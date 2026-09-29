import os

SECRET_KEY = "pantry-development-only-secret-key-000000000000000000000000"
DEBUG = False
ALLOWED_HOSTS = ["localhost", "testserver"]

INSTALLED_APPS = [
    "recipes",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "pantry_site.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PANTRY_DB_NAME", "pantry_dev"),
        "USER": os.environ.get("PANTRY_DB_USER", "pantry"),
        "PASSWORD": os.environ.get("PANTRY_DB_PASSWORD", ""),
        "HOST": os.environ.get("PANTRY_DB_HOST", "postgres"),
        "PORT": 5432,
        "TEST": {"NAME": "pantry_test"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
