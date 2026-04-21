from __future__ import annotations


def default_history_reason_for(history_type: str, verbose_name: str) -> str:
    action = {
        "+": "Created",
        "~": "Updated",
        "-": "Deleted",
    }.get(history_type, "Changed")
    return f"{action} {verbose_name}"


def default_history_reason(record) -> str:
    return default_history_reason_for(
        record.history_type,
        record.instance._meta.verbose_name,
    )


def set_default_history_change_reason(
    sender,
    instance,
    history_instance,
    **kwargs,
) -> None:
    if history_instance.history_change_reason:
        return
    history_instance.history_change_reason = default_history_reason_for(
        history_instance.history_type,
        instance._meta.verbose_name,
    )


def history_reason(record) -> str:
    return record.history_change_reason or default_history_reason(record)


class HistoryReasonMixin:
    history_action = "Updated"

    def get_history_change_reason(self, form) -> str:
        return f"{self.history_action} {form.instance._meta.verbose_name}"

    def form_valid(self, form):
        form.instance._change_reason = self.get_history_change_reason(form)
        return super().form_valid(form)
