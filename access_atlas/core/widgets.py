from django import forms


class DatePicker(forms.TextInput):
    """Text input initialized as a Flatpickr date picker."""

    input_type = "text"

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault("attrs", {})
        attrs["class"] = merge_widget_classes(attrs.get("class"), "date-picker")
        attrs.setdefault("placeholder", "YYYY-MM-DD")
        super().__init__(*args, **kwargs)


class DateTimePicker(forms.TextInput):
    """Text input initialized as a Flatpickr date and time picker."""

    input_type = "text"

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault("attrs", {})
        attrs["class"] = merge_widget_classes(attrs.get("class"), "datetime-picker")
        attrs.setdefault("placeholder", "YYYY-MM-DD hh:mm:ss")
        super().__init__(*args, **kwargs)


class TimePicker(forms.TextInput):
    """Text input initialized as a Flatpickr time picker."""

    input_type = "text"

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault("attrs", {})
        attrs["class"] = merge_widget_classes(attrs.get("class"), "time-picker")
        attrs.setdefault("placeholder", "hh:mm")
        super().__init__(*args, **kwargs)


def merge_widget_classes(*class_values: str | None) -> str:
    """Merge widget CSS class fragments while preserving order."""
    classes: list[str] = []
    for class_value in class_values:
        if not class_value:
            continue
        for css_class in class_value.split():
            if css_class not in classes:
                classes.append(css_class)
    return " ".join(classes)
