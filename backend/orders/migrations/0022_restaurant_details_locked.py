from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0021_order_rejection_reason")]
    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="details_locked",
            field=models.BooleanField(default=False),
        ),
    ]
