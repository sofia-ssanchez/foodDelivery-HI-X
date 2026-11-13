from django.db import migrations


def move_legacy_assignments(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Courier = apps.get_model("delivery", "Courier")
    Assignment = apps.get_model("delivery", "DeliveryAssignment")
    alias = schema_editor.connection.alias
    for order in Order.objects.using(alias).exclude(courier_id=None).iterator():
        courier, _ = Courier.objects.using(alias).get_or_create(user_id=order.courier_id)
        if Assignment.objects.using(alias).filter(order_id=order.id).exists():
            raise RuntimeError(f"Order {order.id} has both legacy and new assignments; reconcile them before migrating.")
        active = order.status in ("ready", "picked_up")
        if active and Assignment.objects.using(alias).filter(
            courier_id=courier.id, status__in=("offered", "accepted")
        ).exists():
            raise RuntimeError(f"Courier {courier.id} has multiple active legacy deliveries; finish them before migrating.")
        assignment_status = "accepted" if active else (
            "completed" if order.status in ("delivered", "refunded", "partially_refunded") else "cancelled"
        )
        # Unknown historical handoff times remain null. offered_at is the time
        # this assignment record was imported, not a fabricated historical offer.
        Assignment.objects.using(alias).create(
            order_id=order.id, courier_id=courier.id, status=assignment_status,
            picked_up_at=order.picked_up_at, delivered_at=order.delivered_at,
        )
        if active:
            Courier.objects.using(alias).filter(pk=courier.id).update(
                status="carrying" if order.status == "picked_up" else "assigned"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0011_order_delivered_at_order_picked_up_at"),
        ("delivery", "0002_deliveryassignment_cancelled_at_and_more"),
    ]
    operations = [
        migrations.RunPython(move_legacy_assignments),
        migrations.RemoveField(model_name="order", name="courier"),
    ]
