
from datetime import timedelta
from decimal import Decimal

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
            role=User.Role.OPERATOR,
        )

        self.customer = User.objects.create_user(
            username="ledger_customer",
            password="password123",
            role=User.Role.CUSTOMER,
        )

        self.restaurant_owner = User.objects.create_user(
            username="ledger_restaurant",
            password="password123",
            role=User.Role.RESTAURANT,
        )

        self.restaurant = Restaurant.objects.create(
            name="Green Garden",
            owner=self.restaurant_owner,
            latitude="45.500000",
            longitude="-73.500000",
        )

        self.menu_item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Vegan Burger",
            price="12.00",
        )

        self.client = APIClient()
        self.url = "/api/pricing/ledger/"

    def create_ledger_entry(self, finalized_at=None):
        """Create an order, its item, and its ledger entry."""
        order = Order.objects.create(
            customer=self.customer,
            restaurant=self.restaurant,
            status=Order.Status.DELIVERED,
        )

        OrderLine.objects.create(
            order=order,
            menu_item=self.menu_item,
            quantity=2,
            unit_price=Decimal("12.00"),
        )

        now = timezone.now()

        ledger_entry = OrderLedger.objects.create(
            order=order,
            final_state=Order.Status.DELIVERED,
            order_created_at=order.created_at,
            finalized_at=finalized_at or now,
            subtotal=Decimal("24.00"),
            delivery_fee=Decimal("3.99"),
            service_fee=Decimal("1.50"),
            small_order_surcharge=Decimal("0.00"),
            total_charge=Decimal("29.49"),
        )

        return ledger_entry

    def create_refund(self, ledger_entry, amount):
        """Create an approved refund and its separate ledger entry."""
        refund_request = RefundRequest.objects.create(
            order=ledger_entry.order,
            customer=self.customer,
            reason=RefundRequest.Reason.OTHER,
            status=RefundRequest.Status.APPROVED,
            approved_amount=Decimal(amount),
            operator=self.operator,
        )

        return RefundLedgerEntry.objects.create(
            original_charge=ledger_entry,
            refund_request=refund_request,
            amount=Decimal(amount),
            operator=self.operator,
        )

    # 1. An operator can access the ledger.

    def test_operator_can_access_ledger(self):
        self.create_ledger_entry()
        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    # 2. A customer cannot access the ledger.

    def test_customer_cannot_access_ledger(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    # 3. An inactive operator cannot access the ledger.

    def test_inactive_operator_cannot_access_ledger(self):
        self.operator.is_active = False
        self.operator.save()

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    # 4. Ledger entries are ordered by finalized_at, newest first.

    def test_ledger_entries_are_ordered_by_finalized_at_descending(self):
        now = timezone.now()

        older_entry = self.create_ledger_entry(
            finalized_at=now - timedelta(days=2)
        )

        newer_entry = self.create_ledger_entry(
            finalized_at=now - timedelta(days=1)
        )

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [entry["order_id"] for entry in response.data],
            [newer_entry.order_id, older_entry.order_id],
        )

    # 5. Refunds are ordered by created_at, oldest first.

    def test_refunds_are_ordered_by_created_at_ascending(self):
        ledger_entry = self.create_ledger_entry()

        first_refund = self.create_refund(
            ledger_entry,
            "2.00",
        )

        second_refund = self.create_refund(
            ledger_entry,
            "3.00",
        )

        now = timezone.now()

        # Set explicit timestamps so the expected order is deterministic.
        RefundLedgerEntry.objects.filter(
            pk=first_refund.pk
        ).update(created_at=now - timedelta(days=1))

        RefundLedgerEntry.objects.filter(
            pk=second_refund.pk
        ).update(created_at=now)

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        refunds = response.data[0]["refunds"]

        self.assertEqual(
            [refund["refund_id"] for refund in refunds],
            [first_refund.id, second_refund.id],
        )

    # 6. The response contains the correct order, restaurant,
    # item, and charge details.

    def test_ledger_response_contains_correct_order_details(self):
        ledger_entry = self.create_ledger_entry()

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        entry = response.data[0]

        self.assertEqual(entry["order_id"], ledger_entry.order_id)
        self.assertEqual(entry["restaurant"], "Green Garden")
        self.assertEqual(entry["final_state"], Order.Status.DELIVERED)
        self.assertEqual(
            entry["current_order_status"],
            Order.Status.DELIVERED,
        )

        self.assertEqual(
            entry["items"],
            [
                {
                    "name": "Vegan Burger",
                    "quantity": 2,
                    "unit_price": "12.00",
                    "line_total": "24.00",
                }
            ],
        )

        self.assertEqual(entry["subtotal"], "24.00")
        self.assertEqual(entry["delivery_fee"], "3.99")
        self.assertEqual(entry["service_fee"], "1.50")
        self.assertEqual(entry["small_order_surcharge"], "0.00")
        self.assertEqual(entry["total_charge"], "29.49")

    # 7. Refund totals and net charge are calculated correctly.

    def test_refund_totals_and_net_charge_are_correct(self):
        ledger_entry = self.create_ledger_entry()

        self.create_refund(
            ledger_entry,
            "5.00",
        )

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        entry = response.data[0]

        self.assertEqual(entry["total_charge"], "29.49")
        self.assertEqual(entry["total_refunded"], "5.00")
        self.assertEqual(entry["net_charge"], "24.49")

    # 8. The response contains the correct refund details.

    def test_ledger_response_contains_refund_details(self):
        ledger_entry = self.create_ledger_entry()

        refund = self.create_refund(
            ledger_entry,
            "5.00",
        )

        self.client.force_authenticate(user=self.operator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        entry = response.data[0]
        refunds = entry["refunds"]

        self.assertEqual(len(refunds), 1)

        self.assertEqual(
            refunds[0]["refund_id"],
            refund.id,
        )

        self.assertEqual(
            refunds[0]["refund_request_id"],
            refund.refund_request_id,
        )

        self.assertEqual(refunds[0]["amount"], "5.00")
        self.assertEqual(
            refunds[0]["operator"],
            self.operator.username,
        )
