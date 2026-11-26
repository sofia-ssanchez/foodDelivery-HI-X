"""Run with: python manage.py test dispatch --verbosity 2."""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from orders.commands import MarkOrderReadyCommand
from orders.models import Order, Restaurant
from delivery.models import Courier, DeliveryAssignment
from rest_framework.test import APIClient
from .services import OrderQueueService
from .events import courier_available_publisher


def make_courier(username, longitude):
    user = User.objects.create(username=username, role=User.Role.COURIER)
    courier = Courier.objects.get(user=user)
    courier.status = Courier.Status.IDLE
    courier.latitude = 0
    courier.longitude = longitude
    courier.save()
    return courier


class onOrderPipelineTests(TestCase):
    def test_ready_order_is_assigned_to_nearest_courier(self):
        owner = User.objects.create(
            username="restaurant", role=User.Role.RESTAURANT,
        )
        customer = User.objects.create(
            username="customer", role=User.Role.CUSTOMER,
        )
        restaurant = Restaurant.objects.create(
            name="Test Restaurant", owner=owner, latitude=0, longitude=0,
        )
        order = Order.objects.create(
            customer=customer,
            restaurant=restaurant,
            status=Order.Status.PREPARING,
        )

        # Create the farther courier first to prove selection uses distance.
        make_courier("far", 2)
        nearest = make_courier("near", 1)
        print("\nSETUP: Created restaurant, preparing order, and two available couriers.", flush=True)
        print("RUN: Mark ready → publisher → dispatcher → courier selection → assignment.", flush=True)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            MarkOrderReadyCommand(
                actor=owner,
                order_id=order.pk,
                expected_status=Order.Status.PREPARING,
            ).execute()
            self.assertFalse(DeliveryAssignment.objects.filter(order=order).exists())
            print("PASS: Assignment waits for the commit callback.", flush=True)

        self.assertGreaterEqual(len(callbacks), 1)
        print("PASS: Executed the order-ready commit callback.", flush=True)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertIsNotNone(order.ready_at)
        print("PASS: Order changed to READY.", flush=True)

        assignment = DeliveryAssignment.objects.get(order=order, status=DeliveryAssignment.Status.OFFERED)
        print("PASS: The pipeline created one active assignment for the order.", flush=True)

        self.assertEqual(assignment.courier, nearest)
        print(f"PASS: Selected nearest courier: {assignment.courier.user.username}.", flush=True)
        print("CLEANUP: Django will roll back these test records and destroy the test database after the run.", flush=True)


class OrderQueueTests(TestCase):
    def test_queue_orders_by_ready_time_then_id_and_excludes_assigned(self):
        user = User.objects.create(username="queue-user")
        restaurant = Restaurant.objects.create(
            name="Queue Restaurant", owner=user, latitude=0, longitude=0,
        )
        now = timezone.now()

        def make_order(status=Order.Status.READY, ready_at=now):
            return Order.objects.create(
                customer=user, restaurant=restaurant,
                status=status, ready_at=ready_at,
            )

        later = make_order(ready_at=now + timedelta(minutes=1))
        first = make_order()
        second = make_order()
        make_order(status=Order.Status.PREPARING, ready_at=None)
        assigned = make_order()
        courier = make_courier("queue-courier", 1)
        DeliveryAssignment.objects.create(order=assigned, courier=courier)
        DeliveryAssignment.objects.create(order=first, courier=courier, status=DeliveryAssignment.Status.CANCELLED)

        self.assertEqual(list(OrderQueueService().get_waiting_orders()), [first, second, later])
        print("PASS: Waiting queue uses ready time, ID tiebreak, and excludes active assignments.", flush=True)


class CourierAvailabilityPipelineTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create(username="observer-customer")
        owner = User.objects.create(username="observer-owner", role=User.Role.RESTAURANT)
        self.restaurant = Restaurant.objects.create(
            name="Observer Restaurant", owner=owner, latitude=0, longitude=0,
        )
        self.courier = make_courier("observer-courier", 1)

    def make_waiting_order(self, ready_at):
        return Order.objects.create(
            customer=self.customer, restaurant=self.restaurant,
            status=Order.Status.READY, ready_at=ready_at,
        )

    def test_notification_assigns_oldest_and_leaves_remaining_order_queued(self):
        now = timezone.now()
        # Reverse creation order so the test distinguishes ready time from ID.
        newer = self.make_waiting_order(now)
        oldest = self.make_waiting_order(now - timedelta(minutes=5))
        print("\nRUN: Courier availability publisher → Dispatcher → oldest waiting order.", flush=True)

        courier_available_publisher.notify(self.courier)

        assignment = DeliveryAssignment.objects.get(courier=self.courier, status=DeliveryAssignment.Status.OFFERED)
        self.assertEqual(assignment.order, oldest)
        self.assertEqual(list(OrderQueueService().get_waiting_orders()), [newer])
        oldest.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(oldest.status, Order.Status.READY)
        self.assertEqual(newer.ready_at, now)
        print("PASS: Oldest-ready order assigned; remaining order retains its queue position.", flush=True)

        courier_available_publisher.notify(self.courier)
        self.assertEqual(DeliveryAssignment.objects.filter(courier=self.courier).count(), 1)
        self.assertEqual(list(OrderQueueService().get_waiting_orders()), [newer])
        print("PASS: Repeated notification cannot give an occupied courier another assignment.", flush=True)

    def test_unavailable_courier_leaves_order_waiting(self):
        order = self.make_waiting_order(timezone.now())
        self.courier.status = Courier.Status.OFFLINE
        self.courier.save(update_fields=["status"])

        courier_available_publisher.notify(self.courier)

        self.assertFalse(DeliveryAssignment.objects.exists())
        self.assertEqual(list(OrderQueueService().get_waiting_orders()), [order])
        print("PASS: Unavailable courier receives no assignment; order remains queued.", flush=True)

    def test_empty_queue_creates_no_assignment(self):
        courier_available_publisher.notify(self.courier)

        self.assertFalse(DeliveryAssignment.objects.exists())
        self.assertFalse(OrderQueueService().get_waiting_orders().exists())
        print("PASS: Available-courier notification handles an empty queue without error.", flush=True)

    def tearDown(self):
        print("CLEANUP: Django will roll back this test's records in the separate test database.", flush=True)


class CourierDutyEndpointTests(CourierAvailabilityPipelineTests):
    def test_duty_endpoint_creates_offer_visible_to_courier(self):
        oldest = self.make_waiting_order(timezone.now() - timedelta(minutes=5))
        newer = self.make_waiting_order(timezone.now())
        self.courier.status = Courier.Status.OFFLINE
        self.courier.save(update_fields=["status"])
        client = APIClient()
        client.force_authenticate(self.courier.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.patch("/api/delivery/duty/", {"on_duty": True}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertFalse(DeliveryAssignment.objects.exists())
        offer = DeliveryAssignment.objects.get(order=oldest)
        self.assertEqual(offer.courier, self.courier)
        self.assertEqual(offer.status, DeliveryAssignment.Status.OFFERED)
        response = client.get("/api/delivery/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["offers"]], [offer.pk])
        self.assertEqual(list(OrderQueueService().get_waiting_orders()), [newer])
        with self.captureOnCommitCallbacks(execute=True):
            response = client.patch("/api/delivery/duty/", {"on_duty": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeliveryAssignment.objects.count(), 1)
        response = client.post(f"/api/delivery/offers/{offer.pk}/accept/")
        self.assertEqual(response.status_code, 200, response.data)
        offer.refresh_from_db()
        self.assertEqual(offer.status, DeliveryAssignment.Status.ACCEPTED)
        print("PASS: Duty endpoint dispatches after commit; courier sees and accepts the same offer.", flush=True)


class StalledOrderTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create(username="stalled-customer")
        self.restaurant = Restaurant.objects.create(
            name="Stalled Restaurant", owner=self.customer, latitude=0, longitude=0,
        )
        self.order = Order.objects.create(
            customer=self.customer, restaurant=self.restaurant,
            status=Order.Status.READY, ready_at=timezone.now() - timedelta(minutes=5),
        )
        self.courier = make_courier("stalled-near", 1)
        self.offer = DeliveryAssignment.objects.create(
            order=self.order, courier=self.courier,
        )
        DeliveryAssignment.objects.filter(pk=self.offer.pk).update(
            offered_at=timezone.now() - timedelta(minutes=3),
        )

    def test_expiration_notifies_after_commit_and_reoffers(self):
        from delivery.commands import expire_delivery_offer
        other = make_courier("stalled-far", 2)
        ready_at = self.order.ready_at
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.assertTrue(expire_delivery_offer(
                assignment_id=self.offer.pk,
                cutoff=timezone.now() - timedelta(minutes=2),
            ))
            self.assertEqual(DeliveryAssignment.objects.filter(order=self.order).count(), 1)
        self.assertEqual(len(callbacks), 1)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, DeliveryAssignment.Status.EXPIRED)
        self.assertIsNotNone(self.offer.expired_at)
        self.assertEqual(DeliveryAssignment.objects.get(
            order=self.order, status=DeliveryAssignment.Status.OFFERED,
        ).courier, other)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.READY)
        self.assertEqual(self.order.ready_at, ready_at)

    def test_cooldown_keeps_order_waiting_then_sweep_retries(self):
        from .tasks import check_stalled_orders
        from .events import dispatcher
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(check_stalled_orders(), 1)
        self.assertTrue(OrderQueueService().get_waiting_orders().filter(pk=self.order.pk).exists())
        self.assertFalse(dispatcher.assign_order_to_courier(self.order, self.courier))
        DeliveryAssignment.objects.filter(pk=self.offer.pk).update(
            expired_at=timezone.now() - timedelta(minutes=3),
        )
        self.assertEqual(check_stalled_orders(), 0)
        self.assertEqual(DeliveryAssignment.objects.get(
            order=self.order, status=DeliveryAssignment.Status.OFFERED,
        ).courier, self.courier)

    def test_accepted_offer_is_not_expired(self):
        from delivery.commands import AcceptOfferCommand, expire_delivery_offer
        AcceptOfferCommand(self.courier.user, self.offer.pk).execute()
        self.assertFalse(expire_delivery_offer(
            assignment_id=self.offer.pk, cutoff=timezone.now(),
        ))
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, DeliveryAssignment.Status.ACCEPTED)

    def test_expired_offer_cannot_be_accepted_and_expiration_is_idempotent(self):
        from delivery.commands import AcceptOfferCommand, DeliveryConflict, expire_delivery_offer
        self.assertTrue(expire_delivery_offer(
            assignment_id=self.offer.pk, cutoff=timezone.now(),
        ))
        self.assertFalse(expire_delivery_offer(
            assignment_id=self.offer.pk, cutoff=timezone.now(),
        ))
        with self.assertRaises(DeliveryConflict):
            AcceptOfferCommand(self.courier.user, self.offer.pk).execute()

    def test_fresh_offer_is_not_expired(self):
        from delivery.commands import expire_delivery_offer
        self.assertFalse(expire_delivery_offer(
            assignment_id=self.offer.pk,
            cutoff=timezone.now() - timedelta(minutes=4),
        ))

    def test_sweep_respects_configured_timeout_and_exact_deadline(self):
        from unittest.mock import patch
        from .tasks import check_stalled_orders

        now = timezone.now()
        with self.settings(DISPATCH_OFFER_TIMEOUT_SECONDS=300):
            with patch("dispatch.tasks.timezone.now", return_value=now):
                self.assertEqual(check_stalled_orders(), 0)
                self.offer.refresh_from_db()
                self.assertEqual(self.offer.status, DeliveryAssignment.Status.OFFERED)

                DeliveryAssignment.objects.filter(pk=self.offer.pk).update(
                    offered_at=now - timedelta(seconds=300),
                )
                with self.captureOnCommitCallbacks(execute=True):
                    self.assertEqual(check_stalled_orders(), 1)
                self.offer.refresh_from_db()
                self.assertEqual(self.offer.status, DeliveryAssignment.Status.EXPIRED)

    def test_sweep_continues_after_conflict_and_retries_waiting_queue(self):
        from unittest.mock import patch
        from delivery.commands import DeliveryConflict, expire_delivery_offer
        from .tasks import check_stalled_orders

        other = make_courier("stalled-other", 2)
        second_order = Order.objects.create(
            customer=self.customer, restaurant=self.restaurant,
            status=Order.Status.READY, ready_at=timezone.now(),
        )
        second_offer = DeliveryAssignment.objects.create(
            order=second_order, courier=other,
        )
        DeliveryAssignment.objects.filter(pk=second_offer.pk).update(
            offered_at=timezone.now() - timedelta(minutes=4),
        )

        def expire_with_conflict(*, assignment_id, cutoff):
            if assignment_id == self.offer.pk:
                raise DeliveryConflict()
            return expire_delivery_offer(assignment_id=assignment_id, cutoff=cutoff)

        with patch("dispatch.tasks.expire_delivery_offer", side_effect=expire_with_conflict):
            with self.assertLogs("dispatch.tasks", level="WARNING"):
                with self.captureOnCommitCallbacks(execute=True):
                    self.assertEqual(check_stalled_orders(), 1)
        self.offer.refresh_from_db()
        second_offer.refresh_from_db()
        self.assertEqual(self.offer.status, DeliveryAssignment.Status.OFFERED)
        self.assertEqual(second_offer.status, DeliveryAssignment.Status.EXPIRED)
        self.assertTrue(
            OrderQueueService().get_waiting_orders().filter(pk=second_order.pk).exists()
        )

        # The conflicted offer is eligible again on the next sweep.
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(check_stalled_orders(), 1)

    def test_sweep_assigns_waiting_orders_oldest_first_without_expirations(self):
        from .tasks import check_stalled_orders

        DeliveryAssignment.objects.filter(pk=self.offer.pk).update(
            status=DeliveryAssignment.Status.DECLINED,
        )
        newer = Order.objects.create(
            customer=self.customer, restaurant=self.restaurant,
            status=Order.Status.READY, ready_at=timezone.now(),
        )
        self.assertEqual(check_stalled_orders(), 0)
        self.assertEqual(
            DeliveryAssignment.objects.get(status=DeliveryAssignment.Status.OFFERED).order,
            self.order,
        )
        self.assertTrue(OrderQueueService().get_waiting_orders().filter(pk=newer.pk).exists())


class StalledOrderCommandTests(TestCase):
    def test_single_sweep_reports_count_without_sleeping(self):
        from io import StringIO
        from unittest.mock import patch
        from django.core.management import call_command

        output = StringIO()
        target = "dispatch.management.commands.check_stalled_orders"
        with patch(f"{target}.check_stalled_orders", return_value=2) as sweep:
            with patch(f"{target}.time.sleep") as sleep:
                call_command("check_stalled_orders", stdout=output)
        sweep.assert_called_once_with()
        sleep.assert_not_called()
        self.assertIn("Expired 2 offer(s).", output.getvalue())

    def test_loop_repeats_and_stops_cleanly_on_interrupt(self):
        from io import StringIO
        from unittest.mock import patch
        from django.core.management import call_command

        output = StringIO()
        target = "dispatch.management.commands.check_stalled_orders"
        with patch(f"{target}.check_stalled_orders", side_effect=[1, 0]) as sweep:
            with patch(f"{target}.time.sleep", side_effect=[None, KeyboardInterrupt]) as sleep:
                call_command("check_stalled_orders", loop=True, interval=5, stdout=output)
        self.assertEqual(sweep.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(5)
        self.assertIn("Expired 1 offer(s).", output.getvalue())
        self.assertIn("Expired 0 offer(s).", output.getvalue())
        self.assertIn("Stopped stalled-order worker.", output.getvalue())

    def test_nonpositive_interval_is_rejected_before_sweep(self):
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError

        target = "dispatch.management.commands.check_stalled_orders.check_stalled_orders"
        with patch(target) as sweep:
            for interval in (0, -1):
                with self.subTest(interval=interval):
                    with self.assertRaisesMessage(CommandError, "--interval must be positive."):
                        call_command("check_stalled_orders", interval=interval)
        sweep.assert_not_called()
