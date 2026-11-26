from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class DeliveryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "delivery"

    def ready(self):
        # Discover signal modules only after Django has loaded all models.
        autodiscover_modules("signals")
