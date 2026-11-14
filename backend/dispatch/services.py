"""Courier lookup and persistent waiting-order queue."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from delivery.models import Courier, DeliveryAssignment
from orders.models import Order

ACTIVE_STATUSES = (DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED)


class CourierService:
    def get_cooling_down_courier_ids(self):
        cutoff = timezone.now() - timedelta(
            seconds=settings.DISPATCH_EXPIRED_COOLDOWN_SECONDS
        )
        return DeliveryAssignment.objects.filter(
            status=DeliveryAssignment.Status.EXPIRED, expired_at__gt=cutoff,
        ).values("courier_id")

    def get_idle_couriers(self) -> list[Courier]:
        return list(
            Courier.objects.select_related("user").filter(
                status=Courier.Status.IDLE,
                user__is_active=True,
                user__role="courier",
                latitude__isnull=False,
                longitude__isnull=False,
            ).exclude(assignments__status__in=ACTIVE_STATUSES)
            .exclude(pk__in=self.get_cooling_down_courier_ids()).order_by("user_id")
        )


class OrderQueueService:
    def get_waiting_orders(self):
        return (
            Order.objects.filter(status=Order.Status.READY)
            .exclude(delivery_assignments__status__in=ACTIVE_STATUSES)
            .order_by("ready_at", "id")
        )
