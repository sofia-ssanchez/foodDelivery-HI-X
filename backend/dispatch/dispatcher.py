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
            self.offer_to_nearest(waiting_order)

    def offer_to_nearest(self, order: Order, *, exclude_courier_id=None) -> None:
        # Reconstruct the current round without deleting decline history. A
        # repeated courier marks the start of a new round of offers.
        declined = set()
        history = DeliveryAssignment.objects.filter(
            order=order, status=DeliveryAssignment.Status.DECLINED,
        ).order_by("id").values_list("courier_id", flat=True)
        for courier_id in history:
            if courier_id in declined:
                declined.clear()
            declined.add(courier_id)
        available = [courier for courier in self.courier_service.get_idle_couriers()
                     if courier.pk != exclude_courier_id]
        couriers = [courier for courier in available if courier.pk not in declined]
        # Everyone currently eligible declined: begin again, nearest first.
        if not couriers:
            couriers = available
        while couriers:
            courier = self.strategy.select_courier(order, couriers)
            if courier is None or self.assign_order_to_courier(order, courier):
                return
            couriers = [candidate for candidate in couriers if candidate.pk != courier.pk]

    def on_offer_declined(self, order_id: int, courier_id: int) -> None:
        order = OrderQueueService().get_waiting_orders().filter(pk=order_id).first()
        if order is not None:
            # Try another courier before restarting the declined order's round.
            self.offer_to_nearest(order, exclude_courier_id=courier_id)

        courier = Courier.objects.filter(pk=courier_id).first()
        if courier is None or not self.verify_availability(courier):
            return
        # Give the declining courier a different job, oldest ready first.
        for alternative in OrderQueueService().get_waiting_orders().exclude(pk=order_id):
            if self.assign_order_to_courier(alternative, courier):
                return
        # No alternative can be assigned: keep the original retry cycle alive.
        order = OrderQueueService().get_waiting_orders().filter(pk=order_id).first()
        if order is not None:
            self.offer_to_nearest(order)

    def on_courier_available(self, courier: Courier) -> None:
        for order in OrderQueueService().get_waiting_orders():
            if not self.verify_availability(courier):
                return
            self.offer_to_nearest(order)
