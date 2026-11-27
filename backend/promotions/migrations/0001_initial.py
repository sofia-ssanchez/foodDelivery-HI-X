import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("orders", "0020_restaurant_address")]
    operations = [
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40)),
                ("discount_type", models.CharField(choices=[("fixed", "Fixed amount"), ("percentage", "Percentage")], default="fixed", max_length=12)),
                ("discount", models.DecimalField(decimal_places=2, max_digits=8)),
                ("minimum_order", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("expires_at", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotions", to="orders.restaurant")),
            ],
            options={"ordering": ["expires_at", "code"]},
        ),
        migrations.AddConstraint(
            model_name="promotion",
            constraint=models.UniqueConstraint(fields=("restaurant", "code"), name="unique_promo_code_per_restaurant"),
        ),
    ]
