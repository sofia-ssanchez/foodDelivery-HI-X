from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Order, Restaurant


class OrderTerminalStateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            username="state_customer", password="password123", role="customer"
        )
        owner = User.objects.create_user(
            username="state_restaurant", password="password123", role="restaurant"
        )
        self.restaurant = Restaurant.objects.create(
            name="State Kitchen",
            owner=owner,
            latitude="45.501700",
            longitude="-73.567300",
        )

    def make_order(self, status):
        return Order.objects.create(
            customer=self.customer,
            restaurant=self.restaurant,
            status=status,
        )

    def test_rejected_and_cancelled_orders_are_terminal_without_events(self):
        for terminal_status in (Order.Status.REJECTED, Order.Status.CANCELLED):
            with self.subTest(status=terminal_status):
                order = self.make_order(terminal_status)

                for target_status in Order.Status.values:
                    with self.subTest(target=target_status):
                        with self.assertRaises(ValueError):
                            order.transition(target_status)

                        self.assertEqual(order.status, terminal_status)
                        order.refresh_from_db()
                        self.assertEqual(order.status, terminal_status)
                        self.assertFalse(order.status_events.exists())

    def test_delivered_order_can_transition_to_refunded(self):
        order = self.make_order(Order.Status.DELIVERED)

        order.transition(Order.Status.REFUNDED)

        self.assertEqual(order.status, Order.Status.REFUNDED)

    def test_valid_partial_refund_path_is_preserved(self):
        order = self.make_order(Order.Status.DELIVERED)

        order.transition(Order.Status.PARTIALLY_REFUNDED)
        order.transition(Order.Status.REFUNDED)

        self.assertEqual(order.status, Order.Status.REFUNDED)
