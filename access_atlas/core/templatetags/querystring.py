from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_update(context, **updates):
    request = context["request"]
    query = request.GET.copy()
    for key, value in updates.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    query_string = query.urlencode()
    return f"?{query_string}" if query_string else ""
