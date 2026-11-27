from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0020_restaurant_address")]
    operations = [
        migrations.AddField(
            model_name="order",
            name="rejection_reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
