"""
Django settings for the AlphaFlow backend.

The backend is a thin service layer over the existing AlphaFlow core
(agents/, tools/, backtest/, graph.py, state.py, config.py). Those modules
are imported unchanged; this project only wraps them in a REST/SSE API.
"""
import os
from pathlib import Path

# BASE_DIR = backend/  ; PROJECT_ROOT = d:\Project\stock_agent (parent, where agents/ etc. live)
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-change-me-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "backend.core",
    "backend.analysis",
    "backend.market",
    "backend.backtests",
    "backend.configapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    },
]

WSGI_APPLICATION = "backend.backend.wsgi.application"
ASGI_APPLICATION = "backend.backend.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # SQLite busy timeout (seconds) — lets the SSE reader wait for a write
        # lock from the orchestrator worker thread instead of raising
        # "database is locked". 20s is generous; analyses take minutes.
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
        "ATOMIC_REQUESTS": False,
    }
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = False  # match the existing codebase (timestamps are naive local time)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- CORS (cross-origin requests from the React dev server) -----------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

# --- AlphaFlow core integration ---------------------------------------------
# The existing modules use a global ConfigManager rooted at PROJECT_ROOT.
# config_default.json / config_user.json / .env live there too.
ALPHAFLOW_PROJECT_ROOT = str(PROJECT_ROOT)
