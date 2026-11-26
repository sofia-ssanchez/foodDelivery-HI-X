from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "delivery"

    def ready(self):
        from . import user_signals  # noqa: F401
        from dispatch import events  # noqa: F401
