import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(needs_autoescape=True)
def highlight_match(value, arg, autoescape=True):
    """Wrap matched query text in a yellow highlight for the global search table."""

    lookup_type, _, query = str(arg).partition("::")
    if not value or not query:
        return conditional_escape(value) if autoescape else value

    raw_value = str(value)
    if lookup_type == "iregex":
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
    else:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    matches = [
        match for match in pattern.finditer(raw_value) if match.end() > match.start()
    ]
    if not matches:
        return conditional_escape(raw_value) if autoescape else raw_value

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        start, end = match.span()
        pieces.append(str(conditional_escape(raw_value[cursor:start])))
        matched_text = conditional_escape(raw_value[start:end])
        pieces.append(f'<mark class="search-match">{matched_text}</mark>')
        cursor = end
    pieces.append(str(conditional_escape(raw_value[cursor:])))
    return mark_safe("".join(pieces))
