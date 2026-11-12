from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


class Courier(models.Model):
    """Delivery profile and operational state for a courier account."""

    class Status(models.TextChoices):
        OFFLINE = "offline", "Offline"
        IDLE = "idle", "Idle"
        ASSIGNED = "assigned", "Assigned"
        CARRYING = "carrying", "Carrying"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courier_profile",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.OFFLINE,
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=Decimal("45.501700"),
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=Decimal("-73.567300"),
    )

    def transition(self, target_status):
        allowed = {
            self.Status.OFFLINE: {self.Status.IDLE, self.Status.ASSIGNED},
            self.Status.IDLE: {self.Status.OFFLINE, self.Status.ASSIGNED},
            self.Status.ASSIGNED: {self.Status.OFFLINE, self.Status.CARRYING},
            self.Status.CARRYING: {self.Status.IDLE},
        }
        if target_status not in allowed[self.status]:
            raise ValueError(
                f"Invalid courier transition from {self.status} to {target_status}."
            )
        self.status = target_status

    def __str__(self):
        return f"Courier {self.user_id} ({self.status})"


class DeliveryAssignment(models.Model):
    """An offer and its outcome; completed rows preserve courier history."""

    class Status(models.TextChoices):
        OFFERED = "offered", "Offered"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        REASSIGNED = "reassigned", "Reassigned"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="delivery_assignments",
    )
    courier = models.ForeignKey(
        Courier,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.OFFERED,
    )
    offered_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-offered_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("courier",),
                condition=Q(status__in=("offered", "accepted")),
                name="one_active_delivery_per_courier",
            ),
            models.UniqueConstraint(
                fields=("order",),
                condition=Q(status__in=("offered", "accepted")),
                name="one_active_courier_per_order",
            ),
        ]

    def __str__(self):
        return f"Order {self.order_id} offered to courier {self.courier_id} ({self.status})"
