"""Run with: python manage.py test orders.dispatch --verbosity 2."""

from django.test import TestCase

from accounts.models import User
from orders.commands import MarkOrderReadyCommand
from orders.models import DeliveryAssignment, Order, Restaurant


class DispatchPipelineTests(TestCase):
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
        print("PASS: Order changed to READY.", flush=True)

        assignment = DeliveryAssignment.objects.get(order=order, is_active=True)
        print("PASS: The pipeline created one active assignment for the order.", flush=True)

        self.assertEqual(assignment.courier, nearest)
        print(f"PASS: Selected nearest courier: {assignment.courier.username}.", flush=True)
        print("CLEANUP: Django will roll back these test records and destroy the test database after the run.", flush=True)
