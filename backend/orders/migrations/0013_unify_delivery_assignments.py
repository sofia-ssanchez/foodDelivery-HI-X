from django.db import migrations


def move_dispatch_assignments(apps, schema_editor):
    Old = apps.get_model('orders', 'DeliveryAssignment')
    Assignment = apps.get_model('delivery', 'DeliveryAssignment')
    Courier = apps.get_model('delivery', 'Courier')
    alias = schema_editor.connection.alias
    for old in Old.objects.using(alias).select_related('order', 'courier').order_by('id'):
        courier, created = Courier.objects.using(alias).get_or_create(user_id=old.courier_id)
        if created:
            if old.courier.latitude is not None and old.courier.longitude is not None:
                courier.latitude = old.courier.latitude
                courier.longitude = old.courier.longitude
        active = old.is_active and old.order.status in ('ready', 'picked_up')
        if active and (
            Assignment.objects.using(alias).filter(order_id=old.order_id, status__in=('offered', 'accepted')).exists()
            or Assignment.objects.using(alias).filter(courier_id=courier.pk, status__in=('offered', 'accepted')).exists()
        ):
            raise RuntimeError(f'Conflicting active assignment for legacy dispatch assignment {old.pk}; reconcile before migrating.')
        if active:
            status = 'accepted' if old.order.status == 'picked_up' else 'offered'
            courier.status = 'carrying' if status == 'accepted' else 'idle'
        else:
            status = 'completed' if old.order.status in ('delivered', 'refunded', 'partially_refunded') else 'cancelled'
        courier.save(using=alias)
        assignment = Assignment.objects.using(alias).create(
            order_id=old.order_id, courier_id=courier.pk, status=status,
            picked_up_at=old.order.picked_up_at, delivered_at=old.order.delivered_at,
        )
        Assignment.objects.using(alias).filter(pk=assignment.pk).update(offered_at=old.assigned_at)


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0010_orderstatusevent'),
        ('orders', '0011_order_ready_at'),
        ('orders', '0012_move_legacy_couriers_to_delivery'),
        ('accounts', '0003_user_is_available'),
    ]
    operations = [
        migrations.RunPython(move_dispatch_assignments),
        migrations.DeleteModel(name='DeliveryAssignment'),
    ]
