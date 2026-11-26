from django.conf import settings
from django.db import models
from django.db.models import Q

class OrderLedger(models.Model):

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="ledger_entry"
    )

    final_state = models.CharField(max_length=20)

    order_created_at = models.DateTimeField()

    finalized_at = models.DateTimeField()

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)

    service_fee = models.DecimalField(max_digits=10, decimal_places=2)

    small_order_surcharge = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    total_charge = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Ledger for Order {self.order_id}"

class RefundRequest(models.Model):

    class Reason(models.TextChoices):
        NOT_RECEIVED = "not_received", "Order never arrived"
        MISSING_ITEMS = "missing_items", "Missing items"
        INCORRECT_ITEMS = "incorrect_items", "Incorrect items"
        DAMAGED_ITEMS = "damaged_items", "Damaged or poor-quality items"
        RESTAURANT_CANCELLED = "restaurant_cancelled", "Cancelled by restaurant"
        REJECTED_ORDER = "rejected_order", "Order rejected"
        DUPLICATE_PAYMENT = "duplicate_payment", "Duplicate payment"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="refund_requests",
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refund_requests",
    )

    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
    )

    details = models.TextField(blank=True)

    requested_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    approved_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    decision_notes = models.TextField(blank=True)

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="decided_refund_requests",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status="pending"),
                name="one_pending_refund_per_order",
            )
        ]

    def __str__(self):
        return f"Refund request for Order {self.order_id}"


class RefundLedgerEntry(models.Model):

    original_charge = models.ForeignKey(
        OrderLedger,
        on_delete=models.PROTECT,
        related_name="refund_entries",
    )

    refund_request = models.OneToOneField(
        RefundRequest,
        on_delete=models.PROTECT,
        related_name="ledger_entry",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_refunds",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Refund of ${self.amount} for Order {self.original_charge.order_id}"