"""Select couriers; delivery commands own offer validation and persistence."""

from delivery.commands import create_delivery_offer, DeliveryConflict
from delivery.models import Courier, DeliveryAssignment
from orders.models import Order
from rest_framework.exceptions import ValidationError
from .interfaces import DispatchStrategy, OrderReadyObserver, CourierAvailabilityObserver
from .services import ACTIVE_STATUSES, CourierService, OrderQueueService
from .strategies import NearestIdleCourierStrategy


class Dispatcher(OrderReadyObserver, CourierAvailabilityObserver):
    def __init__(self, courier_service: CourierService | None = None,
                 strategy: DispatchStrategy | None = None):
        self.courier_service = courier_service if courier_service is not None else CourierService()
        self.strategy = strategy if strategy is not None else NearestIdleCourierStrategy()

    def verify_availability(self, courier: Courier) -> bool:
        return (
            Courier.objects.filter(
                pk=courier.pk, status=Courier.Status.IDLE,
                user__is_active=True, user__role="courier",
                latitude__isnull=False, longitude__isnull=False,
            ).exists()
            and not DeliveryAssignment.objects.filter(
                courier=courier, status__in=ACTIVE_STATUSES,
            ).exists()
        )

    def assign_order_to_courier(self, order: Order, courier: Courier) -> bool:
        if not self.verify_availability(courier):
            return False
        try:
            # This command locks courier then order and rechecks both states.
            create_delivery_offer(order_id=order.pk, courier_id=courier.pk)
        except (DeliveryConflict, ValidationError):
            return False
        return True

    def on_order_ready(self, order: Order) -> None:
        if not OrderQueueService().get_waiting_orders().filter(pk=order.pk).exists():
            return
        # Give older waiting orders priority over the newly ready order.
        for waiting_order in OrderQueueService().get_waiting_orders():
            couriers = self.courier_service.get_idle_couriers()
            while couriers:
                courier = self.strategy.select_courier(waiting_order, couriers)
                if courier is None:
                    break
                if self.assign_order_to_courier(waiting_order, courier):
                    break
                couriers = [candidate for candidate in couriers if candidate.pk != courier.pk]
            if not couriers:
                return

    def on_courier_available(self, courier: Courier) -> None:
        for order in OrderQueueService().get_waiting_orders():
            if not self.verify_availability(courier):
                return
            if self.assign_order_to_courier(order, courier):
                return
