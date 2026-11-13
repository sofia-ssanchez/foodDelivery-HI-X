from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from rest_framework.test import APIClient

from delivery.commands import (
    AcceptOfferCommand,
    ChangeDutyCommand,
    ConfirmDeliveryCommand,
    ConfirmPickupCommand,
    create_delivery_offer,
)
from delivery.models import Courier, DeliveryAssignment
from .commands import (
    AcceptOrderCommand,
    CustomerCancelOrderCommand,
    MarkOrderReadyCommand,
    PlaceOrderCommand,
    StartPreparationCommand,
)
from .models import MenuItem, Order, OrderLine, OrderStatusEvent, Restaurant
from .address_lookup import SALT


class OrderStatusEventTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            username="event_customer", password="password123", role="customer"
        )
        self.restaurant_user = User.objects.create_user(
            username="event_restaurant", password="password123", role="restaurant"
        )
        self.courier_user = User.objects.create_user(
            username="event_courier", password="password123", role="courier"
        )
        self.restaurant = Restaurant.objects.create(
            name="Event Kitchen",
            owner=self.restaurant_user,
            latitude="45.501700",
            longitude="-73.567300",
        )
        self.item = MenuItem.objects.create(
            restaurant=self.restaurant, name="Soup", price="8.00"
        )

    def place_order(self):
        return PlaceOrderCommand(
            customer=self.customer,
            restaurant_id=self.restaurant.id,
            items=[{"menu_item_id": self.item.id, "quantity": 1}],
            delivery_address_token=signing.dumps(
                {
                    "customer_id": self.customer.pk,
                    "address": "123 Demo Street, Montreal, QC",
                    "latitude": "45.501700",
                    "longitude": "-73.567300",
                },
                salt=SALT,
            ),
        ).execute()

    def assert_event(self, order, number, old, new, actor):
        event = order.status_events.get(transition_number=number)
        self.assertEqual(event.event_id, f"evt-{order.id}-{number}")
        self.assertEqual(event.from_status, old)
        self.assertEqual(event.to_status, new)
        self.assertEqual(event.actor, actor)
        self.assertEqual(event.actor_username, actor.username)
        self.assertEqual(event.actor_role, actor.role)
        return event

    def test_order_lifecycle_records_each_actor_and_transition(self):
        order = self.place_order()
        self.assert_event(order, 1, "", Order.Status.PLACED, self.customer)

        client = APIClient()
        client.force_authenticate(user=self.restaurant_user)
        for expected, target in (
            (Order.Status.PLACED, Order.Status.ACCEPTED),
            (Order.Status.ACCEPTED, Order.Status.PREPARING),
            (Order.Status.PREPARING, Order.Status.READY),
        ):
            response = client.patch(
                f"/api/restaurant/orders/{order.id}/status/",
                {"expected_status": expected, "status": target},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)

        self.assert_event(order, 2, "placed", "accepted", self.restaurant_user)
        self.assert_event(order, 3, "accepted", "preparing", self.restaurant_user)
        self.assert_event(order, 4, "preparing", "ready", self.restaurant_user)

        courier = Courier.objects.get(user=self.courier_user)
        courier.status = Courier.Status.IDLE
        courier.save(update_fields=["status"])
        assignment = create_delivery_offer(order_id=order.id, courier_id=courier.id)
        AcceptOfferCommand(self.courier_user, assignment.id).execute()
        ConfirmPickupCommand(self.courier_user, assignment.id).execute()
        ConfirmDeliveryCommand(self.courier_user, assignment.id).execute()

        self.assert_event(order, 5, "ready", "picked_up", self.courier_user)
        self.assert_event(order, 6, "picked_up", "delivered", self.courier_user)
        self.assertEqual(OrderStatusEvent.objects.filter(order=order).count(), 6)

    def test_cancellation_records_event_and_invalidates_pending_offer_atomically(self):
        order = self.place_order()
        client = APIClient()
        client.force_authenticate(user=self.restaurant_user)
        client.patch(
            f"/api/restaurant/orders/{order.id}/status/",
            {"expected_status": "placed", "status": "accepted"},
            format="json",
        )
        client.patch(
            f"/api/restaurant/orders/{order.id}/status/",
            {"expected_status": "accepted", "status": "preparing"},
            format="json",
        )
        client.patch(
            f"/api/restaurant/orders/{order.id}/status/",
            {"expected_status": "preparing", "status": "ready"},
            format="json",
        )
        courier = Courier.objects.get(user=self.courier_user)
        courier.status = Courier.Status.IDLE
        courier.save(update_fields=["status"])
        assignment = create_delivery_offer(order_id=order.id, courier_id=courier.id)

        operator = get_user_model().objects.create_user(
            username="event_operator", password="password123", role="operator"
        )
        client.force_authenticate(user=operator)
        response = client.post(
            f"/api/operator/orders/{order.id}/cancel/",
            {"expected_status": "ready"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.Status.CANCELLED)
        self.assert_event(order, 5, "ready", "cancelled", operator)

    def test_event_failure_rolls_back_order_placement(self):
        with patch(
            "orders.commands.record_order_status_event",
            side_effect=RuntimeError("event write failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.place_order()

        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderLine.objects.exists())

    def test_event_failure_rolls_back_restaurant_transition(self):
        order = self.place_order()
        with patch(
            "orders.commands.record_order_status_event",
            side_effect=RuntimeError("event write failed"),
        ):
            with self.assertRaises(RuntimeError):
                from .commands import AcceptOrderCommand

                AcceptOrderCommand(
                    actor=self.restaurant_user,
                    order_id=order.id,
                    expected_status=Order.Status.PLACED,
                ).execute()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PLACED)
        self.assertEqual(order.status_events.count(), 1)

    def test_customer_cancellation_records_event(self):
        order = self.place_order()
        CustomerCancelOrderCommand(
            actor=self.customer,
            order_id=order.id,
            expected_status=Order.Status.PLACED,
        ).execute()
        self.assert_event(order, 2, "placed", "cancelled", self.customer)

    def test_delivery_event_failure_rolls_back_delivery_state(self):
        order = self.place_order()
        for command_class, expected in (
            (AcceptOrderCommand, Order.Status.PLACED),
            (StartPreparationCommand, Order.Status.ACCEPTED),
            (MarkOrderReadyCommand, Order.Status.PREPARING),
        ):
            command_class(
                actor=self.restaurant_user,
                order_id=order.id,
                expected_status=expected,
            ).execute()

        ChangeDutyCommand(self.courier_user, True).execute()
        courier = Courier.objects.get(user=self.courier_user)
        assignment = create_delivery_offer(order_id=order.id, courier_id=courier.id)
        AcceptOfferCommand(self.courier_user, assignment.id).execute()

        with patch(
            "delivery.commands.record_order_status_event",
            side_effect=RuntimeError("event write failed"),
        ):
            with self.assertRaises(RuntimeError):
                ConfirmPickupCommand(
                    self.courier_user, assignment.id
                ).execute()

        order.refresh_from_db()
        courier.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertEqual(courier.status, Courier.Status.ASSIGNED)
        self.assertEqual(assignment.status, DeliveryAssignment.Status.ACCEPTED)
        self.assertIsNone(assignment.picked_up_at)
        self.assertEqual(order.status_events.count(), 4)
