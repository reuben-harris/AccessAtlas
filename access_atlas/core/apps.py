from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "access_atlas.core"
    label = "core"

    def ready(self) -> None:
        from simple_history.signals import pre_create_historical_record

        from access_atlas.core.history import set_default_history_change_reason

        pre_create_historical_record.connect(
            set_default_history_change_reason,
            dispatch_uid="access_atlas.default_history_change_reason",
        )
