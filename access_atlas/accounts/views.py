from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmailLoginForm
from .models import User


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = EmailLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
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
        login(request, user)
        return redirect("dashboard")

    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
