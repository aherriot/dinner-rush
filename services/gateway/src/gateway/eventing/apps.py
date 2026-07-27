from django.apps import AppConfig


class EventingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gateway.eventing"
    label = "eventing"
