from django.db import models


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