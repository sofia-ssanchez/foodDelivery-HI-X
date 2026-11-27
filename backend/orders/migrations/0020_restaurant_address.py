from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0019_rename_pricing_snapshot_payment_details")]
    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="address",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
    ]
