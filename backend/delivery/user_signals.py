from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Courier


@receiver(post_save, sender=get_user_model())
def ensure_courier_profile(sender, instance, **kwargs):
    if instance.role == instance.Role.COURIER:
        Courier.objects.get_or_create(user=instance)
