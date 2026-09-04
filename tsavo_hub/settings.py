import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.contrib.messages import constants as message_constants
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path):
    """Load a simple KEY=VALUE file without overriding process environment."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"").strip("'")
        os.environ.setdefault(key.strip(), value)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


load_env_file(BASE_DIR / ".env")

DEBUG = env_bool("DEBUG", True)
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False.")
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "anymail",
    "core",
    "accounts",
    "innovators",
    "attendance",
    "dashboard",
    "auditlog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.ForceFirstLoginPasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.CustomNotFoundMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "tsavo_hub.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "tsavo_hub.wsgi.application"
ASGI_APPLICATION = "tsavo_hub.asgi.application"


def database_from_url(url):
    if not url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    parsed = urlparse(url)
    if parsed.scheme in {"sqlite", "sqlite3"}:
        if parsed.path in {"", "/"}:
            name = BASE_DIR / "db.sqlite3"
        else:
            raw_path = unquote(parsed.path)
            if raw_path == "/:memory:":
                return {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
            if raw_path.startswith("//"):
                raw_path = raw_path[1:]
                name = Path(raw_path)
            elif raw_path.startswith("/") and len(raw_path) > 3 and raw_path[2] == ":":
                raw_path = raw_path[1:]
                name = Path(raw_path)
            else:
                name = BASE_DIR / raw_path.lstrip("/")
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": name}
    if parsed.scheme not in {"postgres", "postgresql", "pgsql"}:
        raise ImproperlyConfigured("DATABASE_URL must use sqlite or postgresql.")
    options = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": parsed.port or "",
        "CONN_MAX_AGE": 60,
    }
    if options:
        config["OPTIONS"] = options
    return config


DATABASES = {"default": database_from_url(os.getenv("DATABASE_URL", ""))}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
STORAGES = {
    "default": {
        "BACKEND": (
            "core.storage.CloudinaryMediaStorage"
            if CLOUDINARY_URL
            else "django.core.files.storage.FileSystemStorage"
        )
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT") or BASE_DIR / "media")
# Bump this value for deployments that change local CSS or JavaScript. The
# version is appended to shared asset URLs so browsers do not reuse stale files.
STATIC_VERSION = os.getenv("STATIC_VERSION", "20260903.1")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "accounts:login"
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "3600"))
MESSAGE_TAGS = {message_constants.ERROR: "danger"}

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
ANYMAIL = {"BREVO_API_KEY": BREVO_API_KEY}
DEFAULT_EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "anymail.backends.brevo.EmailBackend"
)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", DEFAULT_EMAIL_BACKEND)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "Tsavo Innovation & Incubation Hub <noreply@secora.dev>",
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "accounts.services": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if env_bool("TRUST_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SITE_LOGO_URL = os.getenv("SITE_LOGO_URL", "")
