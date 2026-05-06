from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
AUTH_MODE_LOCAL = "local"
AUTH_MODE_OIDC = "oidc"
AUTH_MODE_LOCAL_OIDC = "local-oidc"
AUTH_MODE_CHOICES = {AUTH_MODE_LOCAL, AUTH_MODE_OIDC, AUTH_MODE_LOCAL_OIDC}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-secret-key")
DEBUG = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
AUTH_MODE = os.getenv("AUTH_MODE", AUTH_MODE_LOCAL).lower()
if AUTH_MODE not in AUTH_MODE_CHOICES:
    msg = (
        "AUTH_MODE must be one of "
        f"{', '.join(sorted(AUTH_MODE_CHOICES))}; got {AUTH_MODE!r}."
    )
    raise ValueError(msg)
LOCAL_LOGIN_ENABLED = AUTH_MODE in {AUTH_MODE_LOCAL, AUTH_MODE_LOCAL_OIDC}
OIDC_LOGIN_ENABLED = AUTH_MODE in {AUTH_MODE_OIDC, AUTH_MODE_LOCAL_OIDC}
OIDC_PROVIDER_ID = os.getenv("OIDC_PROVIDER_ID", "access-atlas")
OIDC_PROVIDER_NAME = os.getenv("OIDC_PROVIDER_NAME", "Single Sign-On")
OIDC_SERVER_URL = os.getenv("OIDC_SERVER_URL", "")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_TOKEN_AUTH_METHOD = os.getenv("OIDC_TOKEN_AUTH_METHOD", "")
OIDC_FETCH_USERINFO = os.getenv("OIDC_FETCH_USERINFO", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OIDC_PKCE_ENABLED = os.getenv("OIDC_PKCE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
if OIDC_LOGIN_ENABLED and not all(
    [OIDC_SERVER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET]
):
    msg = (
        "AUTH_MODE enables OIDC, so OIDC_SERVER_URL, OIDC_CLIENT_ID, "
        "and OIDC_CLIENT_SECRET must be set."
    )
    raise ValueError(msg)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "django_tomselect",
    "simple_history",
    "storages",
    "access_atlas.accounts.apps.AccountsConfig",
    "access_atlas.core.apps.CoreConfig",
    "access_atlas.sites.apps.SitesConfig",
    "access_atlas.jobs.apps.JobsConfig",
    "access_atlas.trips.apps.TripsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_tomselect.middleware.TomSelectMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "access_atlas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "access_atlas.accounts.context_processors.theme_preference",
                "access_atlas.core.context_processors.active_nav_item",
                "access_atlas.core.context_processors.bug_report",
            ],
        },
    },
]

WSGI_APPLICATION = "access_atlas.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_PROVIDERS = {}
if OIDC_LOGIN_ENABLED:
    oidc_app_settings = {
        "server_url": OIDC_SERVER_URL,
        "fetch_userinfo": OIDC_FETCH_USERINFO,
        "oauth_pkce_enabled": OIDC_PKCE_ENABLED,
    }
    if OIDC_TOKEN_AUTH_METHOD:
        oidc_app_settings["token_auth_method"] = OIDC_TOKEN_AUTH_METHOD
    SOCIALACCOUNT_PROVIDERS = {
        "openid_connect": {
            "OAUTH_PKCE_ENABLED": OIDC_PKCE_ENABLED,
            "APPS": [
                {
                    "provider_id": OIDC_PROVIDER_ID,
                    "name": OIDC_PROVIDER_NAME,
                    "client_id": OIDC_CLIENT_ID,
                    "secret": OIDC_CLIENT_SECRET,
                    "settings": oidc_app_settings,
                }
            ],
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Pacific/Auckland")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / os.getenv("MEDIA_ROOT", "media")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_STORAGE_BACKEND = os.getenv("MEDIA_STORAGE_BACKEND", "local").lower()
if MEDIA_STORAGE_BACKEND == "s3":
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
    if not AWS_STORAGE_BUCKET_NAME:
        raise ValueError(
            "MEDIA_STORAGE_BACKEND=s3 requires AWS_STORAGE_BUCKET_NAME to be set."
        )
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "")
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "")
    AWS_QUERYSTRING_AUTH = os.getenv("AWS_QUERYSTRING_AUTH", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    AWS_DEFAULT_ACL = None
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
elif MEDIA_STORAGE_BACKEND != "local":
    raise ValueError("MEDIA_STORAGE_BACKEND must be either 'local' or 's3'.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_SITE_FEED_URL = "http://127.0.0.1:8000/dummy/site-feed.json"
SITE_FEED_URL = os.getenv("SITE_FEED_URL") or DEFAULT_SITE_FEED_URL
SITE_FEED_TOKEN = os.getenv("SITE_FEED_TOKEN") or "dev-token"
DEFAULT_BUG_REPORT_URL = "https://github.com/reuben-harris/AccessAtlas/issues/new"
BUG_REPORT_URL = os.getenv("BUG_REPORT_URL", DEFAULT_BUG_REPORT_URL).strip()

MAP_TILE_URL = os.getenv(
    "MAP_TILE_URL",
    "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
)
MAP_TILE_DARK_URL = os.getenv(
    "MAP_TILE_DARK_URL",
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
)
MAP_TILE_ATTRIBUTION = os.getenv(
    "MAP_TILE_ATTRIBUTION",
    (
        '&copy; <a href="https://www.openstreetmap.org/copyright">'
        "OpenStreetMap</a> contributors &copy; "
        '<a href="https://carto.com/attributions">CARTO</a>'
    ),
)
MAP_TILE_DARK_ATTRIBUTION = os.getenv(
    "MAP_TILE_DARK_ATTRIBUTION",
    MAP_TILE_ATTRIBUTION,
)
MAP_TILE_MAX_ZOOM = int(os.getenv("MAP_TILE_MAX_ZOOM", "19"))
