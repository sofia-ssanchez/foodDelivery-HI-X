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
        # Keep response expectations independent of deployment pricing settings.
        config_patch = patch("pricing.services.load_pricing_config", return_value={
            "delivery_fee": "3.99",
            "service_fee": "1.50",
            "small_order_threshold": "15.00",
            "small_order_surcharge": "2.00",
        })
        config_patch.start()
        self.addCleanup(config_patch.stop)
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
        # Check delivered order totals.
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subtotal"], "24.00")
        self.assertEqual(response.data["total"], "29.49")
        self.assertEqual(response.data["items"][0]["quantity"], 2)

    def test_summary_before_delivery(self):
        # Block summaries before delivery.
        self.order.status = "ready"
        self.order.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 409)

    def test_customer_cannot_view_other_orders(self):
        # Hide other customers' orders.
        User = get_user_model()

        other_customer = User.objects.create_user(
            username="other_customer",
            password="password123",
            role="customer"
        )

        self.client.force_authenticate(user=other_customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_complete_summary_response(self):
        # Verify every response field.
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "order_id": self.order.id,
            "restaurant": "Green Garden",
            "status": "delivered",
            "created_at": self.order.created_at.isoformat().replace("+00:00", "Z"),
            "items": [{
                "name": "Vegan Burger",
                "quantity": 2,
                "unit_price": "12.00",
                "line_total": "24.00",
            }],
            "subtotal": "24.00",
            "delivery_fee": "3.99",
            "service_fee": "1.50",
            "small_order_surcharge": "0.00",
            "total": "29.49",
        })

    def test_refunded_statuses_allow_summary(self):
        # Allow summaries after refunds.
        for order_status in (Order.Status.PARTIALLY_REFUNDED, Order.Status.REFUNDED):
            with self.subTest(status=order_status):
                self.order.status = order_status
                self.order.save()

                response = self.client.get(self.url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["status"], order_status)
                self.assertEqual(response.data["total"], "29.49")

    def test_all_non_summary_statuses_return_conflict(self):
        # Reject all unsupported statuses.
        for order_status in (
            Order.Status.PLACED, Order.Status.ACCEPTED, Order.Status.REJECTED,
            Order.Status.PREPARING, Order.Status.READY, Order.Status.PICKED_UP,
            Order.Status.CANCELLED,
        ):
            with self.subTest(status=order_status):
                self.order.status = order_status
                self.order.save()

                response = self.client.get(self.url)

                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json(), {
                    "detail": "Order summary is available after delivery."
                })

    def test_missing_order_returns_not_found(self):
        # Return 404 for missing orders.
        missing_id = self.order.id + 1
        self.assertFalse(Order.objects.filter(pk=missing_id).exists())

        response = self.client.get(f"/api/pricing/orders/{missing_id}/summary/")

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_is_denied(self):
        # Require customer login.
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_non_customer_roles_are_denied(self):
        # Reject non-customer accounts.
        User = get_user_model()
        for role in (User.Role.RESTAURANT, User.Role.COURIER, User.Role.OPERATOR):
            with self.subTest(role=role):
                user = User.objects.create_user(username=f"summary_{role}_access", role=role)
                self.client.force_authenticate(user=user)

                response = self.client.get(self.url)

                self.assertEqual(response.status_code, 403)

    def test_inactive_customer_is_denied(self):
        # Reject inactive customers.
        self.customer.is_active = False
        self.customer.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_small_order_summary_includes_surcharge(self):
        # Include small-order surcharge.
        self.order.lines.update(quantity=1)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subtotal"], "12.00")
        self.assertEqual(response.data["small_order_surcharge"], "2.00")
        self.assertEqual(response.data["total"], "19.49")
        self.assertEqual(response.data["items"][0]["line_total"], "12.00")

    def test_multiple_items_use_order_prices(self):
        # Preserve saved prices across items.
        MenuItem.objects.filter(restaurant=self.order.restaurant).update(price="99.00")
        item = MenuItem.objects.create(
            restaurant=self.order.restaurant, name="Soup", price="9.00"
        )
        OrderLine.objects.create(
            order=self.order, menu_item=item, quantity=3, unit_price="4.25"
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.data["items"], [
            {"name": "Vegan Burger", "quantity": 2,
             "unit_price": "12.00", "line_total": "24.00"},
            {"name": "Soup", "quantity": 3,
             "unit_price": "4.25", "line_total": "12.75"},
        ])
        self.assertEqual(response.data["subtotal"], "36.75")
        self.assertEqual(response.data["total"], "42.24")
