from django.urls import path

from access_atlas.api import token_views

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("preferences/", views.preference_view, name="account_preference"),
    path("api-tokens/", token_views.api_token_list_view, name="api_token_list"),
    path(
        "api-tokens/new/",
        token_views.api_token_create_view,
        name="api_token_create",
    ),
    path(
        "api-tokens/<int:pk>/revoke/",
        token_views.api_token_revoke_view,
        name="api_token_revoke",
    ),
]
