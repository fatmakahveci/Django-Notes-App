"""Django settings; local development defaults with environment-based deployment."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Local defaults. Production requires DEBUG=false and a private secret key.

DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() in {'1', 'true', 'yes'}
configured_secret_key = os.getenv('DJANGO_SECRET_KEY')
if not DEBUG and not configured_secret_key:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set when DEBUG is disabled.')
SECRET_KEY = configured_secret_key or "django-insecure-local-development-only-do-not-use-in-production"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

# Enable only behind the private production proxy, which overwrites these headers.
TRUST_PROXY_HEADERS = os.getenv('DJANGO_TRUST_PROXY_HEADERS', 'false').lower() in {'1', 'true', 'yes'}
if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REDIRECT_EXEMPT = [r'^health/$']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tinymce',
    'notes.apps.NotesConfig',
]

MIDDLEWARE = [
    'notes.middleware.TrustedProxyMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # Bound uploads before CSRF middleware parses multipart request bodies.
    'notes.middleware.UploadLimitMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Run after CSRF checks so rejected submissions do not consume login quotas.
    'notes.middleware.AuthenticationThrottleMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DJANGO_DATABASE_PATH', BASE_DIR / 'db.sqlite3'),
    }
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# django-tinymce 5.0.0 bundles an older editor. Serve the patched local assets
# for both public forms and Django admin, without the unused compressor API.
TINYMCE_JS_URL = STATIC_URL + 'vendor/tinymce-7.9.3/tinymce.min.js'
TINYMCE_DEFAULT_CONFIG = {
    'theme': 'silver',
    'height': 380,
    'menubar': False,
    'browser_spellcheck': True,
    'plugins': 'lists link',
    'toolbar': 'undo redo | blocks | bold italic | bullist numlist | link | removeformat',
}

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
CSRF_FAILURE_VIEW = "notes.operations.csrf_failure"

# Fixed windows, shared by public and admin login. All POST attempts count.
AUTH_ATTEMPT_LIMITS = {
    "login": [("ip", 20, 600), ("username", 10, 600)],
    "signup": [("ip", 5, 3600)],
}

# File bytes are excluded from Django's DATA_UPLOAD_MAX_MEMORY_SIZE check.
NOTE_UPLOAD_MAX_BYTES = 25 * 1024 * 1024
NOTE_REQUEST_MAX_BYTES = 26 * 1024 * 1024  # Allow multipart headers and form fields.
