
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from orders.models import Order, OrderLine, Restaurant, MenuItem
from pricing.models import OrderLedger, RefundRequest, RefundLedgerEntry


class OperatorLedgerViewTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.operator = User.objects.create_user(
            username="ledger_operator",
            password="password123",
            role="operator"
        )

        self.customer = User.objects.create_user(
            username="ledger_customer",
            password="password123",
            role="customer"
        )

        self.restaurant_owner = User.objects.create_user(
            username="ledger_restaurant",
            password="password123",
            role="restaurant"
        )

        self.restaurant = Restaurant.objects.create(
            name="Green Garden",
            owner=self.restaurant_owner,
            latitude="45.500000",
            longitude="-73.500000"
        )

        self.item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Vegan Burger",
            price="12.00"
        )

        self.client = APIClient()
        self.url = "/api/pricing/ledger/"

        self.order, self.ledger = self.create_ledger_entry(
            finalized_at=timezone.now()
        )

    def create_ledger_entry(self, finalized_at):
        order = Order.objects.create(
            customer=self.customer,
            restaurant=self.restaurant,
            status="delivered"
        )

        OrderLine.objects.create(
            order=order,
            menu_item=self.item,
            quantity=2,
            unit_price=Decimal("12.00")
        )

        ledger = OrderLedger.objects.create(
            order=order,
            final_state="delivered",
            order_created_at=order.created_at,
            finalized_at=finalized_at,
            subtotal=Decimal("24.00"),
            delivery_fee=Decimal("3.99"),
            service_fee=Decimal("1.50"),
            small_order_surcharge=Decimal("0.00"),
            total_charge=Decimal("29.49")
        )

        return order, ledger

    def test_operator_can_access_ledger(self):
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_access_ledger(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_ledger_entries_are_ordered_by_finalized_at_descending(self):
        older_order, older_ledger = self.create_ledger_entry(
            finalized_at=timezone.now() - timedelta(days=2)
        )

        newer_order, newer_ledger = self.create_ledger_entry(
            finalized_at=timezone.now() - timedelta(days=1)
        )

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        order_ids = [
            entry["order_id"]
            for entry in response.data
        ]

        self.assertEqual(
            order_ids,
            [self.order.id, newer_order.id, older_order.id]
        )

    def test_refund_totals_and_net_charge_are_correct(self):
        refund_request = RefundRequest.objects.create(
            order=self.order,
            customer=self.customer,
            reason="missing_items",
            status="approved",
            requested_amount=Decimal("5.00"),
            approved_amount=Decimal("5.00"),
            operator=self.operator
        )

        RefundLedgerEntry.objects.create(
            original_charge=self.ledger,
            refund_request=refund_request,
            amount=Decimal("5.00"),
            operator=self.operator
        )

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        entry = response.data[0]

        self.assertEqual(entry["total_charge"], "29.49")
        self.assertEqual(entry["total_refunded"], "5.00")
        self.assertEqual(entry["net_charge"], "24.49")

    def test_ledger_response_contains_correct_order_details(self):
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        entry = response.data[0]

        self.assertEqual(entry["order_id"], self.order.id)
        self.assertEqual(entry["restaurant"], "Green Garden")
        self.assertEqual(entry["final_state"], "delivered")
        self.assertEqual(entry["current_order_status"], "delivered")

        self.assertEqual(
            entry["items"],
            [
                {
                    "name": "Vegan Burger",
                    "quantity": 2,
                    "unit_price": "12.00",
                    "line_total": "24.00"
                }
            ]
        )

        self.assertEqual(entry["subtotal"], "24.00")
        self.assertEqual(entry["delivery_fee"], "3.99")
        self.assertEqual(entry["service_fee"], "1.50")
        self.assertEqual(entry["small_order_surcharge"], "0.00")
        self.assertEqual(entry["total_charge"], "29.49")

        self.assertEqual(entry["refunds"], [])
        self.assertEqual(entry["total_refunded"], "0.00")
        self.assertEqual(entry["net_charge"], "29.49")

        self.assertIn("order_created_at", entry)
        self.assertIn("finalized_at", entry)
