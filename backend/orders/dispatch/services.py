"""Courier lookup services."""

from accounts.models import User


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
