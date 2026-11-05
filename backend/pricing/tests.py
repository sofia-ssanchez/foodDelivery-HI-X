##tests that our calculations are correct
## Total = Subtotal + Delivery Fee + Service Fee + Surcharge


from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from .services import calculate_order_pricing
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from orders.models import Order, OrderLine, Restaurant, MenuItem



class PricingTests(SimpleTestCase):

    def calculate(self, items):
        lines = [
            SimpleNamespace(quantity=quantity, unit_price=Decimal(price))
            for quantity, price in items
        ]

        order = SimpleNamespace(
            lines=SimpleNamespace(all=lambda: lines)
        )

        config = {
            "delivery_fee": "3.99",
            "service_fee": "1.50",
            "small_order_threshold": "15.00",
            "small_order_surcharge": "2.00"
        }

        with patch("pricing.services.load_pricing_config", return_value=config):
            return calculate_order_pricing(order)

    def test_regular_order(self):
        result = self.calculate([(2, "12.00")])

        self.assertEqual(result["subtotal"], Decimal("24.00"))
        self.assertEqual(result["total"], Decimal("29.49"))

    def test_small_order(self):
        result = self.calculate([(1, "10.00")])

        self.assertEqual(result["small_order_surcharge"], Decimal("2.00"))
        self.assertEqual(result["total"], Decimal("17.49"))

    def test_order_at_threshold(self):
        result = self.calculate([(1, "15.00")])

        self.assertEqual(result["small_order_surcharge"], Decimal("0.00"))
        self.assertEqual(result["total"], Decimal("20.49"))

    def test_multiple_items(self):
        result = self.calculate([(2, "8.00"), (1, "5.00")])

        self.assertEqual(result["subtotal"], Decimal("21.00"))
        self.assertEqual(result["total"], Decimal("26.49"))

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            self.calculate([(0, "12.00")])

    def test_deterministic_pricing(self):
        items = [(2, "12.00"), (1, "5.00")]

        self.assertEqual(self.calculate(items), self.calculate(items))



class OrderSummaryTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.customer = User.objects.create_user(
            username="summary_customer",
            password="password123",
            role="customer"
        )

        owner = User.objects.create_user(
            username="summary_restaurant",
            password="password123",
            role="restaurant"
        )

        restaurant = Restaurant.objects.create(
            name="Green Garden",
            owner=owner,
            latitude="45.500000",
            longitude="-73.500000"
        )

        item = MenuItem.objects.create(
            restaurant=restaurant,
            name="Vegan Burger",
            price="12.00"
        )

        self.order = Order.objects.create(
            customer=self.customer,
            restaurant=restaurant,
            status="delivered"
        )

        OrderLine.objects.create(
            order=self.order,
            menu_item=item,
            quantity=2,
            unit_price="12.00"
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.customer)
        self.url = f"/api/pricing/orders/{self.order.id}/summary/"

    def test_delivered_order_summary(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subtotal"], "24.00")
        self.assertEqual(response.data["total"], "29.49")
        self.assertEqual(response.data["items"][0]["quantity"], 2)

    def test_summary_before_delivery(self):
        self.order.status = "ready"
        self.order.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 409)

    def test_customer_cannot_view_other_orders(self):
        User = get_user_model()

        other_customer = User.objects.create_user(
            username="other_customer",
            password="password123",
            role="customer"
        )

        self.client.force_authenticate(user=other_customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
