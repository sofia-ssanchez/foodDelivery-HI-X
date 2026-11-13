"""Courier lookup and waiting-order queue services."""

from accounts.models import User
from orders.models import Order


class CourierService:
    """Service for looking up available couriers."""

    def get_idle_couriers(self) -> list[User]:
        couriers = (
            User.objects.filter(
                role=User.Role.COURIER,
                is_active=True,
                is_available=True,
                latitude__isnull=False,
                longitude__isnull=False,
            )
            .exclude(delivery_assignments__is_active=True)
            .order_by("id")
        )

        return list(couriers)


class OrderQueueService:
    def get_waiting_orders(self):
        """Return unassigned ready orders, oldest ready time first."""
        return (
            Order.objects.filter(status=Order.Status.READY)
            .exclude(delivery_assignments__is_active=True)
            .order_by("ready_at", "id")
        )
