from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from orders.commands import MarkOrderReadyCommand
from orders.models import MenuItem, Order, OrderLine, Restaurant
from pricing.models import OrderLedger

from . import events
from .commands import (
    DeliveryConflict,
    ReassignDeliveryCommand,
    create_delivery_offer,
)
from .models import Courier, DeliveryAssignment


class DeliveryLifecycleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            username="delivery_customer", password="password123", role="customer"
        )
        self.owner = User.objects.create_user(
            username="delivery_restaurant", password="password123", role="restaurant"
        )
        self.operator = User.objects.create_user(
            username="delivery_operator", password="password123", role="operator"
        )
        self.courier_user = User.objects.create_user(
            username="delivery_courier", password="password123", role="courier"
        )
        self.other_courier_user = User.objects.create_user(
            username="delivery_other_courier", password="password123", role="courier"
        )
        self.courier = Courier.objects.get(user=self.courier_user)
        self.other_courier = Courier.objects.get(user=self.other_courier_user)
        self.restaurant = Restaurant.objects.create(
            name="Test Kitchen",
            owner=self.owner,
            latitude="45.501700",
            longitude="-73.567300",
        )
        self.item = MenuItem.objects.create(
            restaurant=self.restaurant, name="Soup", price="8.00"
        )
        self.order = self.make_order()
        self.client = APIClient()
        self.client.force_authenticate(user=self.courier_user)
        self.urls = {
            "activity": "/api/delivery/me/",
            "duty": "/api/delivery/duty/",
        }

    def make_order(self, status=Order.Status.READY):
        order = Order.objects.create(
            customer=self.customer,
            restaurant=self.restaurant,
            status=status,
        )
        OrderLine.objects.create(
            order=order, menu_item=self.item, quantity=1, unit_price=self.item.price
        )
        return order

    def go_on_duty(self):
        response = self.client.patch(self.urls["duty"], {"on_duty": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def offer(self, order=None, courier=None):
        return create_delivery_offer(
            order_id=(order or self.order).id,
            courier_id=(courier or self.courier).id,
        )

    def test_new_courier_accounts_get_a_profile_offline(self):
        self.assertEqual(self.courier.status, Courier.Status.OFFLINE)
        self.assertEqual(str(self.courier.latitude), "45.501700")
        self.assertEqual(str(self.courier.longitude), "-73.567300")

    def test_duty_on_and_off_and_idempotent_updates(self):
        self.go_on_duty()
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.IDLE)
        self.go_on_duty()
        response = self.client.patch(self.urls["duty"], {"on_duty": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Courier.Status.OFFLINE)

    def test_offer_can_only_be_created_for_ready_order_and_idle_courier(self):
        with self.assertRaises(DeliveryConflict):
            self.offer()

        self.go_on_duty()
        placed = self.make_order(Order.Status.PLACED)
        with self.assertRaises(ValidationError):
            self.offer(placed)
        self.assertFalse(DeliveryAssignment.objects.filter(order=placed).exists())

    def test_acceptance_assigns_exactly_one_order_and_hides_other_couriers_offers(self):
        self.go_on_duty()
        assignment = self.offer()
        other = APIClient()
        other.force_authenticate(user=self.other_courier_user)
        response = other.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.assertEqual(response.status_code, 409)

        response = self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], DeliveryAssignment.Status.ACCEPTED)
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.ASSIGNED)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.READY)
        duplicate_accept = self.client.post(
            f"/api/delivery/offers/{assignment.id}/accept/"
        )
        self.assertEqual(duplicate_accept.status_code, 409)

        another_order = self.make_order()
        with self.assertRaises(DeliveryConflict):
            self.offer(another_order)

    def test_decline_releases_offer_and_emits_dispatch_event(self):
        self.go_on_duty()
        assignment = self.offer()
        from unittest.mock import patch
        with patch.object(events.delivery_offer_declined, "send_robust") as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/api/delivery/offers/{assignment.id}/decline/"
                )
        self.assertEqual(response.status_code, 200)
        send.assert_called_once_with(
            sender=DeliveryAssignment,
            assignment_id=assignment.id,
            order_id=self.order.id,
            courier_id=self.courier.id,
        )
        self.assertEqual(response.data["status"], DeliveryAssignment.Status.DECLINED)
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.IDLE)
        self.assertFalse(
            DeliveryAssignment.objects.filter(
                courier=self.courier,
                status__in=(DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED),
            ).exists()
        )

    def test_cancelled_ready_order_invalidates_only_pending_offer(self):
        self.go_on_duty()
        offer = self.offer()

        operator_client = APIClient()
        operator_client.force_authenticate(user=self.operator)
        response = operator_client.post(
            f"/api/operator/orders/{self.order.id}/cancel/",
            {"expected_status": Order.Status.READY},
            format="json",
        )

        offer.refresh_from_db()
        self.courier.refresh_from_db()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.CANCELLED)
        self.assertEqual(offer.status, DeliveryAssignment.Status.CANCELLED)
        self.assertIsNotNone(offer.cancelled_at)
        self.assertEqual(self.courier.status, Courier.Status.IDLE)
        self.assertTrue(OrderLedger.objects.filter(order=self.order).exists())
        response = self.client.get(self.urls["activity"])
        self.assertEqual(response.data["offers"], [])
        response = self.client.post(f"/api/delivery/offers/{offer.id}/accept/")
        self.assertEqual(response.status_code, 409)

    def test_order_cancellation_is_rejected_after_acceptance_and_rolls_back(self):
        self.go_on_duty()
        offer = self.offer()
        response = self.client.post(f"/api/delivery/offers/{offer.id}/accept/")
        self.assertEqual(response.status_code, 200)

        operator_client = APIClient()
        operator_client.force_authenticate(user=self.operator)
        response = operator_client.post(
            f"/api/operator/orders/{self.order.id}/cancel/",
            {"expected_status": Order.Status.READY},
            format="json",
        )

        offer.refresh_from_db()
        self.courier.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.order.status, Order.Status.READY)
        self.assertEqual(offer.status, DeliveryAssignment.Status.ACCEPTED)
        self.assertIsNone(offer.cancelled_at)
        self.assertEqual(self.courier.status, Courier.Status.ASSIGNED)
        self.assertFalse(OrderLedger.objects.filter(order=self.order).exists())

    def test_operator_cancellation_ledger_failure_rolls_back_order_and_offer(self):
        self.go_on_duty()
        offer = self.offer()
        operator_client = APIClient()
        operator_client.force_authenticate(user=self.operator)

        from unittest.mock import patch
        with patch(
            "orders.commands.record_order_ledger",
            side_effect=RuntimeError("simulated PRC failure"),
        ):
            with self.assertRaises(RuntimeError):
                operator_client.post(
                    f"/api/operator/orders/{self.order.id}/cancel/",
                    {"expected_status": Order.Status.READY},
                    format="json",
                )

        self.order.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.READY)
        self.assertEqual(offer.status, DeliveryAssignment.Status.OFFERED)
        self.assertIsNone(offer.cancelled_at)
        self.assertFalse(OrderLedger.objects.filter(order=self.order).exists())

    def test_restaurant_has_no_cancellation_command(self):
        self.go_on_duty()
        offer = self.offer()
        restaurant_client = APIClient()
        restaurant_client.force_authenticate(user=self.owner)
        response = restaurant_client.patch(
            f"/api/restaurant/orders/{self.order.id}/status/",
            {"status": Order.Status.CANCELLED, "expected_status": Order.Status.READY},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.READY)
        self.assertEqual(offer.status, DeliveryAssignment.Status.OFFERED)

    def test_customer_can_cancel_own_placed_order(self):
        placed = self.make_order(Order.Status.PLACED)
        customer_client = APIClient()
        customer_client.force_authenticate(user=self.customer)
        response = customer_client.post(
            f"/api/customer/orders/{placed.id}/cancel/"
        )

        self.assertEqual(response.status_code, 200, response.data)
        placed.refresh_from_db()
        self.assertEqual(placed.status, Order.Status.CANCELLED)
        self.assertTrue(OrderLedger.objects.filter(order=placed).exists())

    def test_customer_cannot_cancel_another_customers_order(self):
        User = get_user_model()
        other_customer = User.objects.create_user(
            username="other_order_customer", password="password123", role="customer"
        )
        other_order = Order.objects.create(
            customer=other_customer,
            restaurant=self.restaurant,
            status=Order.Status.PLACED,
        )
        customer_client = APIClient()
        customer_client.force_authenticate(user=self.customer)
        response = customer_client.post(
            f"/api/customer/orders/{other_order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 404)
        other_order.refresh_from_db()
        self.assertEqual(other_order.status, Order.Status.PLACED)

    def test_customer_cannot_cancel_order_after_placement(self):
        customer_client = APIClient()
        customer_client.force_authenticate(user=self.customer)
        response = customer_client.post(
            f"/api/customer/orders/{self.order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.READY)

    def test_only_operator_can_cancel_after_placement(self):
        accepted = self.make_order(Order.Status.ACCEPTED)
        restaurant_client = APIClient()
        restaurant_client.force_authenticate(user=self.owner)
        response = restaurant_client.post(
            f"/api/operator/orders/{accepted.id}/cancel/",
            {"expected_status": Order.Status.ACCEPTED},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        operator_client = APIClient()
        operator_client.force_authenticate(user=self.operator)
        response = operator_client.post(
            f"/api/operator/orders/{accepted.id}/cancel/",
            {"expected_status": Order.Status.ACCEPTED},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        accepted.refresh_from_db()
        self.assertEqual(accepted.status, Order.Status.CANCELLED)

    def test_duty_off_declines_pending_offer_and_cannot_go_offline_while_carrying(self):
        self.go_on_duty()
        assignment = self.offer()
        response = self.client.patch(self.urls["duty"], {"on_duty": False}, format="json")
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.Status.DECLINED)

        self.go_on_duty()
        assignment = self.offer()
        self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.client.post(f"/api/delivery/assignments/{assignment.id}/pickup/")
        response = self.client.patch(self.urls["duty"], {"on_duty": False}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.CARRYING)

    def test_going_offline_keeps_accepted_assignment_for_operator_reassignment(self):
        self.go_on_duty()
        assignment = self.offer()
        response = self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.assertEqual(response.status_code, 200)

        response = self.client.patch(self.urls["duty"], {"on_duty": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Courier.Status.OFFLINE)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.Status.ACCEPTED)
        self.assertIsNone(assignment.cancelled_at)
        self.assertEqual(Order.objects.get(pk=assignment.order_id).status, Order.Status.READY)
        self.assertFalse(
            DeliveryAssignment.objects.filter(
                order_id=assignment.order_id,
                status=DeliveryAssignment.Status.OFFERED,
            ).exists()
        )

        response = self.client.patch(self.urls["duty"], {"on_duty": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Courier.Status.ASSIGNED)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.Status.ACCEPTED)

    def test_operator_reassignment_replaces_only_an_offline_couriers_accepted_order(self):
        self.go_on_duty()
        assignment = self.offer()
        self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.client.patch(self.urls["duty"], {"on_duty": False}, format="json")
        self.other_courier.status = Courier.Status.IDLE
        self.other_courier.save(update_fields=["status"])

        with self.assertRaises(PermissionDenied):
            ReassignDeliveryCommand(
                actor=self.customer,
                assignment_id=assignment.id,
                courier_id=self.other_courier.id,
            ).execute()

        reassigned = ReassignDeliveryCommand(
            actor=self.operator,
            assignment_id=assignment.id,
            courier_id=self.other_courier.id,
        ).execute()
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.Status.REASSIGNED)
        self.assertEqual(reassigned.order_id, assignment.order_id)
        self.assertEqual(reassigned.courier_id, self.other_courier.id)
        self.assertEqual(reassigned.status, DeliveryAssignment.Status.OFFERED)

    def test_operator_reassignment_is_exposed_as_an_operator_only_endpoint(self):
        self.go_on_duty()
        assignment = self.offer()
        self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.client.patch(self.urls["duty"], {"on_duty": False}, format="json")
        Courier.objects.filter(pk=self.other_courier.pk).update(status=Courier.Status.IDLE)
        response = self.client.post(
            f"/api/delivery/operator/assignments/{assignment.id}/reassign/",
            {"courier_id": self.other_courier.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        operator_client = APIClient()
        operator_client.force_authenticate(self.operator)
        response = operator_client.post(
            f"/api/delivery/operator/assignments/{assignment.id}/reassign/",
            {"courier_id": self.other_courier.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], DeliveryAssignment.Status.OFFERED)

    def test_pickup_then_delivery_use_order_transitions_and_record_ledger_once(self):
        self.go_on_duty()
        assignment = self.offer()
        self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")

        response = self.client.post(f"/api/delivery/assignments/{assignment.id}/pickup/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.PICKED_UP)
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.CARRYING)
        first_pickup_time = DeliveryAssignment.objects.get(pk=assignment.pk).picked_up_at
        duplicate_pickup = self.client.post(
            f"/api/delivery/assignments/{assignment.id}/pickup/"
        )
        self.assertEqual(duplicate_pickup.status_code, 409)
        self.assertEqual(
            DeliveryAssignment.objects.get(pk=assignment.pk).picked_up_at,
            first_pickup_time,
        )

        from unittest.mock import patch
        with patch.object(events.courier_became_idle, "send_robust") as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/api/delivery/assignments/{assignment.id}/deliver/"
                )
        self.assertEqual(response.status_code, 200, response.data)
        send.assert_called_once_with(
            sender=DeliveryAssignment,
            courier_id=self.courier.id,
        )
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.DELIVERED)
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.IDLE)
        self.assertEqual(OrderLedger.objects.filter(order=self.order).count(), 1)
        self.assertEqual(
            DeliveryAssignment.objects.get(pk=assignment.pk).status,
            DeliveryAssignment.Status.COMPLETED,
        )

        response = self.client.post(f"/api/delivery/assignments/{assignment.id}/deliver/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(OrderLedger.objects.filter(order=self.order).count(), 1)

    def test_ledger_failure_rolls_back_delivery_state_changes(self):
        from unittest.mock import patch

        self.go_on_duty()
        assignment = self.offer()
        self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.client.post(f"/api/delivery/assignments/{assignment.id}/pickup/")

        with patch(
            "delivery.commands.record_order_ledger",
            side_effect=RuntimeError("simulated PRC failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(f"/api/delivery/assignments/{assignment.id}/deliver/")

        self.order.refresh_from_db()
        self.courier.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PICKED_UP)
        self.assertEqual(self.courier.status, Courier.Status.CARRYING)
        self.assertEqual(assignment.status, DeliveryAssignment.Status.ACCEPTED)
        self.assertIsNone(assignment.delivered_at)
        self.assertFalse(OrderLedger.objects.filter(order=self.order).exists())

    def test_pickup_and_delivery_reject_wrong_order_state(self):
        self.go_on_duty()
        assignment = self.offer()
        self.client.post(f"/api/delivery/offers/{assignment.id}/accept/")
        self.order.status = Order.Status.PREPARING
        self.order.save(update_fields=["status"])

        response = self.client.post(f"/api/delivery/assignments/{assignment.id}/pickup/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Courier.objects.get(pk=self.courier.pk).status, Courier.Status.ASSIGNED)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.PREPARING)

    def test_activity_shows_only_this_couriers_offer_and_active_assignment(self):
        self.go_on_duty()
        assignment = self.offer()
        response = self.client.get(self.urls["activity"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["offers"]], [assignment.id])
        self.assertIsNone(response.data["active_assignment"])
        self.assertNotIn("total", response.data["offers"][0])

    def test_non_courier_cannot_use_courier_endpoints(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.urls["activity"])
        self.assertEqual(response.status_code, 403)

    def test_order_ready_event_is_emitted_after_ord_transition(self):
        self.order.status = Order.Status.PREPARING
        self.order.save(update_fields=["status"])
        from unittest.mock import patch
        with patch.object(events.order_became_ready, "send_robust") as send:
            with self.captureOnCommitCallbacks(execute=True):
                MarkOrderReadyCommand(
                    actor=self.owner,
                    order_id=self.order.id,
                    expected_status=Order.Status.PREPARING,
                ).execute()
                self.assertEqual(
                    Order.objects.get(pk=self.order.pk).status, Order.Status.READY
                )
        send.assert_called_once()


class ConcurrentDeliveryActionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            username="race_customer", password="password123", role="customer"
        )
        self.owner = User.objects.create_user(
            username="race_restaurant", password="password123", role="restaurant"
        )
        self.courier_user = User.objects.create_user(
            username="race_courier", password="password123", role="courier"
        )
        self.courier = Courier.objects.get(user=self.courier_user)
        restaurant = Restaurant.objects.create(
            name="Race Kitchen",
            owner=self.owner,
            latitude="45.501700",
            longitude="-73.567300",
        )
        item = MenuItem.objects.create(restaurant=restaurant, name="Meal", price="12.00")
        self.order = Order.objects.create(
            customer=self.customer,
            restaurant=restaurant,
            status=Order.Status.READY,
        )
        OrderLine.objects.create(
            order=self.order, menu_item=item, quantity=1, unit_price=item.price
        )
        # This concurrency fixture creates its own offer below. Set the seeded
        # courier idle directly so the real availability hook does not dispatch
        # the ready order before the test arranges its simultaneous requests.
        Courier.objects.filter(pk=self.courier.pk).update(status=Courier.Status.IDLE)
        self.courier.refresh_from_db()
        self.assignment = create_delivery_offer(
            order_id=self.order.id,
            courier_id=self.courier.id,
        )

    def concurrent_posts(self, path):
        barrier = Barrier(2)

        def post_action():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.courier_user.pk)
                client = APIClient()
                client.force_authenticate(user=user)
                barrier.wait(timeout=5)
                response = client.post(path)
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: post_action(), range(2)))
        return results

    def assert_one_success_one_conflict(self, statuses):
        self.assertCountEqual(
            [status_code for status_code, _ in statuses],
            [200, 409],
            msg=f"concurrent responses: {statuses!r}",
        )

    def test_acceptance_racing_expiration_has_one_winner(self):
        from django.utils import timezone
        from .commands import AcceptOfferCommand, expire_delivery_offer
        barrier = Barrier(2)
        cutoff = timezone.now()

        def perform(accept):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                if accept:
                    AcceptOfferCommand(self.courier_user, self.assignment.pk).execute()
                    return True
                return expire_delivery_offer(
                    assignment_id=self.assignment.pk, cutoff=cutoff,
                )
            except DeliveryConflict:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(perform, [True, False]))
        self.assertEqual(sum(results), 1)
        self.assignment.refresh_from_db()
        self.courier.refresh_from_db()
        self.assertIn(self.assignment.status, [
            DeliveryAssignment.Status.ACCEPTED, DeliveryAssignment.Status.EXPIRED,
        ])
        expected = (Courier.Status.ASSIGNED
                    if self.assignment.status == DeliveryAssignment.Status.ACCEPTED
                    else Courier.Status.IDLE)
        self.assertEqual(self.courier.status, expected)

    def test_concurrent_acceptance_has_one_winner(self):
        statuses = self.concurrent_posts(
            f"/api/delivery/offers/{self.assignment.id}/accept/"
        )
        self.assert_one_success_one_conflict(statuses)
        self.courier.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertEqual(self.courier.status, Courier.Status.ASSIGNED)
        self.assertEqual(self.assignment.status, DeliveryAssignment.Status.ACCEPTED)
        self.assertEqual(
            DeliveryAssignment.objects.filter(
                courier=self.courier,
                status__in=(DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED),
            ).count(),
            1,
        )

    def test_concurrent_pickup_has_one_winner(self):
        from .commands import AcceptOfferCommand
        AcceptOfferCommand(actor=self.courier_user, assignment_id=self.assignment.id).execute()

        statuses = self.concurrent_posts(
            f"/api/delivery/assignments/{self.assignment.id}/pickup/"
        )
        self.assert_one_success_one_conflict(statuses)
        self.order.refresh_from_db()
        self.courier.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PICKED_UP)
        self.assertEqual(self.courier.status, Courier.Status.CARRYING)
        self.assertIsNotNone(self.assignment.picked_up_at)

    def test_concurrent_delivery_has_one_winner_and_one_ledger(self):
        from .commands import AcceptOfferCommand, ConfirmPickupCommand
        AcceptOfferCommand(actor=self.courier_user, assignment_id=self.assignment.id).execute()
        ConfirmPickupCommand(actor=self.courier_user, assignment_id=self.assignment.id).execute()

        statuses = self.concurrent_posts(
            f"/api/delivery/assignments/{self.assignment.id}/deliver/"
        )
        self.assert_one_success_one_conflict(statuses)
        self.order.refresh_from_db()
        self.courier.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DELIVERED)
        self.assertEqual(self.courier.status, Courier.Status.IDLE)
        self.assertEqual(self.assignment.status, DeliveryAssignment.Status.COMPLETED)
        self.assertEqual(OrderLedger.objects.filter(order=self.order).count(), 1)
