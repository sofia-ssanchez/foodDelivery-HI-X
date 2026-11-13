"""Coordinate courier selection and assignment for ready orders."""

from django.db import transaction

from accounts.models import User
from orders.models import DeliveryAssignment, Order
from .interfaces import DispatchStrategy, OrderReadyObserver
from .services import CourierService
from .strategies import NearestIdleCourierStrategy


class Dispatcher(OrderReadyObserver):
    def __init__(
        self,
        courier_service: CourierService | None = None,
        strategy: DispatchStrategy | None = None,
    ):
        self.courier_service = (
            courier_service if courier_service is not None else CourierService()
        )
        self.strategy = (
            strategy if strategy is not None else NearestIdleCourierStrategy()
        )

    def verify_availability(self, courier: User) -> bool:
        """Check a freshly loaded courier; the caller handles locking."""
        occupied = DeliveryAssignment.objects.filter(
            courier=courier,
            is_active=True,
        ).exists()

        return (
            courier.role == User.Role.COURIER
            and courier.is_active
            and courier.is_available
            and courier.latitude is not None
            and courier.longitude is not None
            and not occupied
        )

    @transaction.atomic
    def on_order_ready(self, order: Order) -> None:
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status != Order.Status.READY:
            return

        if DeliveryAssignment.objects.filter(order=order, is_active=True).exists():
            return

        couriers = self.courier_service.get_idle_couriers()

        while couriers:
            courier = self.strategy.select_courier(order, couriers)
            if courier is None:
                return

            courier = User.objects.select_for_update().get(pk=courier.pk)
            if self.verify_availability(courier):
                DeliveryAssignment.objects.create(order=order, courier=courier)
                return

            couriers = [
                candidate for candidate in couriers if candidate.pk != courier.pk
            ]

        # No eligible courier: leave the order READY and unassigned for retry.
