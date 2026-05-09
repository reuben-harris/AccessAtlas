from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "access_atlas.api"

    def ready(self) -> None:
        # Import schema extensions so drf-spectacular can discover them.
        from . import schema  # noqa: F401
