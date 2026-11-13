from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.

class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        RESTAURANT = "restaurant", "Restaurant"
        COURIER = "courier", "Courier"
        OPERATOR = "operator", "Operator"

    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    role = models.CharField(
        max_length = 30,
        choices = Role.choices,
        default = Role.CUSTOMER,
    )