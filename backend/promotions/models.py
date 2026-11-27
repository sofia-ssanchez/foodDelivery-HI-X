from django.db import models


class Promotion(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENTAGE = "percentage", "Percentage"

    restaurant = models.ForeignKey(
        "orders.Restaurant", on_delete=models.CASCADE, related_name="promotions"
    )
    code = models.CharField(max_length=40)
    discount_type = models.CharField(max_length=12, choices=DiscountType.choices, default=DiscountType.FIXED)
    discount = models.DecimalField(max_digits=8, decimal_places=2)
    minimum_order = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("restaurant", "code"), name="unique_promo_code_per_restaurant")]
        ordering = ["expires_at", "code"]

    def __str__(self):
        return f"{self.code} ({self.restaurant.name})"
