from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.

class User(AbstractUser):
    class Role(models.textChoices):
        CUSTOMER = "customer", "Customer"
        RESTAURANT = "restaurant", "Restaurant"
        COURIER = "courier", "Courier"
        OPERATOR = "operator", "Operator"

        role = models.CharField(
            max_length = 30,
            choices = Role.choices,
            default = Role.CUSTOMER,
        )