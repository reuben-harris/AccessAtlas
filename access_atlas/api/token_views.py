from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from access_atlas.core.mixins import SearchablePaginatedListMixin, SortableListMixin

from .forms import ApiTokenCreateForm
from .models import ApiToken
from .token_services import create_api_token, revoke_api_token

CREATED_TOKEN_SESSION_KEY = "created_api_token"

TOKEN_SORT_FIELDS = {
    "name": "name",
    "prefix": "key_prefix",
    "access": "can_write",
    "expires": "expires_at",
    "last-used": "last_used_at",
    "status": "revoked_at",
}


class ApiTokenListView(
    SortableListMixin,
    SearchablePaginatedListMixin,
    LoginRequiredMixin,
    ListView,
):
    model = ApiToken
    template_name = "accounts/api_token_list.html"
    context_object_name = "tokens"
    search_fields = ("name", "key_prefix")
    search_placeholder = "Search name or prefix"
    sort_preference_page_key = "api-tokens"
    default_sort = "name"
    sort_field_map = TOKEN_SORT_FIELDS

    def get_queryset(self):
        queryset = ApiToken.objects.filter(user=self.request.user)
        queryset = self.apply_search(queryset)
        sort_value = self.get_sort_value()
        sort_prefix = "-" if sort_value.startswith("-") else ""
        sort_key = sort_value.removeprefix("-")
        sort_field = self.sort_field_map.get(sort_key, self.sort_field_map["name"])
        return queryset.order_by(f"{sort_prefix}{sort_field}", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plaintext_token"] = self.request.session.pop(
            CREATED_TOKEN_SESSION_KEY,
            "",
        )
        return context


api_token_list_view = ApiTokenListView.as_view()


@login_required
def api_token_create_view(request):
    form = ApiTokenCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _token, plaintext_token = create_api_token(
            user=request.user,
            name=form.cleaned_data["name"],
            can_write=form.cleaned_data["can_write"],
            expires_at=form.cleaned_data["expires_at"],
        )
        request.session[CREATED_TOKEN_SESSION_KEY] = plaintext_token
        return redirect("api_token_list")
    return render(
        request,
        "accounts/api_token_create.html",
        {"form": form},
    )


@login_required
@require_POST
def api_token_revoke_view(request, pk):
    token = get_object_or_404(ApiToken, pk=pk, user=request.user)
    if token.is_revoked:
        messages.info(request, "API token is already revoked.")
    else:
        revoke_api_token(token)
        messages.success(request, "API token revoked.")
    query_string = request.GET.urlencode()
    list_url = reverse("api_token_list")
    if query_string:
        return redirect(f"{list_url}?{query_string}")
    return redirect(list_url)
