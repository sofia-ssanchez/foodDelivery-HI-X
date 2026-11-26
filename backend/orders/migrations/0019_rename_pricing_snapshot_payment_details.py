from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0018_order_pricing_snapshot"),
    ]

    operations = [
        migrations.RenameField(
            model_name="order",
            old_name="pricing_snapshot",
            new_name="payment_details",
        ),
    ]
