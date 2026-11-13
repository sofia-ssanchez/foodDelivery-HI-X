"""Courier lookup and persistent waiting-order queue."""

from delivery.models import Courier, DeliveryAssignment
from orders.models import Order

ACTIVE_STATUSES = (DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED)


class CourierService:
    def get_idle_couriers(self) -> list[Courier]:
        return list(
            Courier.objects.select_related("user").filter(
                status=Courier.Status.IDLE,
                user__is_active=True,
                user__role="courier",
                latitude__isnull=False,
                longitude__isnull=False,
            ).exclude(assignments__status__in=ACTIVE_STATUSES).order_by("user_id")
        )


class OrderQueueService:
    def get_waiting_orders(self):
        return (
            Order.objects.filter(status=Order.Status.READY)
            .exclude(delivery_assignments__status__in=ACTIVE_STATUSES)
            .order_by("ready_at", "id")
        )
