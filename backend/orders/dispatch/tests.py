"""Run with: python manage.py test orders.dispatch --verbosity 2."""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from orders.commands import MarkOrderReadyCommand
from orders.models import DeliveryAssignment, Order, Restaurant
from .services import OrderQueueService
from .events import courier_available_publisher


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
        User.objects.create(
            username="far", role=User.Role.COURIER, is_available=True,
            latitude=0, longitude=2,
        )
        nearest = User.objects.create(
            username="near", role=User.Role.COURIER, is_available=True,
            latitude=0, longitude=1,
        )
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

        self.assertEqual(len(callbacks), 1)
        print("PASS: Executed the order-ready commit callback.", flush=True)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.READY)
        self.assertIsNotNone(order.ready_at)
        print("PASS: Order changed to READY.", flush=True)

        assignment = DeliveryAssignment.objects.get(order=order, is_active=True)
        print("PASS: The pipeline created one active assignment for the order.", flush=True)

        self.assertEqual(assignment.courier, nearest)
        print(f"PASS: Selected nearest courier: {assignment.courier.username}.", flush=True)
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
        courier = User.objects.create(username="queue-courier", role=User.Role.COURIER)
        DeliveryAssignment.objects.create(order=assigned, courier=courier)
        DeliveryAssignment.objects.create(order=first, courier=courier, is_active=False)

        self.assertEqual(list(OrderQueueService().get_waiting_orders()), [first, second, later])
        print("PASS: Waiting queue uses ready time, ID tiebreak, and excludes active assignments.", flush=True)


class CourierAvailabilityPipelineTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create(username="observer-customer")
        owner = User.objects.create(username="observer-owner", role=User.Role.RESTAURANT)
        self.restaurant = Restaurant.objects.create(
            name="Observer Restaurant", owner=owner, latitude=0, longitude=0,
        )
        self.courier = User.objects.create(
            username="observer-courier", role=User.Role.COURIER,
            is_available=True, latitude=0, longitude=1,
        )

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

        assignment = DeliveryAssignment.objects.get(courier=self.courier, is_active=True)
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
        self.courier.is_available = False
        self.courier.save(update_fields=["is_available"])

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
