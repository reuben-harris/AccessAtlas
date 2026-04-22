import json

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmailLoginForm
from .models import User
from .preferences import set_user_preference


def login_context(form: EmailLoginForm) -> dict[str, object]:
    oidc_login_url = None
    if settings.OIDC_LOGIN_ENABLED:
        oidc_login_url = reverse(
            "openid_connect_login",
            args=[settings.OIDC_PROVIDER_ID],
        )
    return {
        "form": form,
        "local_login_enabled": settings.LOCAL_LOGIN_ENABLED,
        "oidc_login_enabled": settings.OIDC_LOGIN_ENABLED,
        "oidc_login_url": oidc_login_url,
        "oidc_provider_name": settings.OIDC_PROVIDER_NAME,
    }


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = EmailLoginForm(request.POST or None)
    if request.method == "POST" and not settings.LOCAL_LOGIN_ENABLED:
        form.add_error(None, "Local email login is disabled.")
    elif request.method == "POST" and form.is_valid():
        email = User.objects.normalize_email(form.cleaned_data["email"])
        defaults = {}
        if form.cleaned_data["display_name"]:
            defaults["display_name"] = form.cleaned_data["display_name"]
        user, created = User.objects.get_or_create(email=email, defaults=defaults)
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        elif form.cleaned_data["display_name"] and not user.display_name:
            user.display_name = form.cleaned_data["display_name"]
            user.save(update_fields=["display_name"])
        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return redirect("dashboard")

    return render(request, "accounts/login.html", login_context(form))


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
@require_POST
def preference_view(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    key = payload.get("key")
    value = payload.get("value")
    if not isinstance(key, str):
        return JsonResponse({"error": "Preference key is required."}, status=400)

    try:
        preference = set_user_preference(request.user, key, value)
    except ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)

    return JsonResponse({"key": preference.key, "value": preference.value})
