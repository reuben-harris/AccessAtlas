from django import template
from django.forms import CheckboxInput, Select, SelectMultiple
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def field_widget_type(field) -> str:
    return field.field.widget.__class__.__name__


@register.filter
def render_form_field(field):
    widget = field.field.widget
    css_class = "form-control"
    if isinstance(widget, (Select, SelectMultiple)):
        css_class = "form-select"
    elif isinstance(widget, CheckboxInput):
        css_class = "form-check-input"
    if field.errors:
        css_class = f"{css_class} is-invalid"
    return field.as_widget(attrs={"class": css_class})


@register.simple_tag
def required_marker(field):
    """Render the shared required-field marker beside visible field labels."""
    if field.field.required:
        return mark_safe(
            '<span class="form-required-marker" aria-label="required">*</span>'
        )
    return ""
