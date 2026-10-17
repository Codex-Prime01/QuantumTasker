"""
Django settings for Quantum Manager.

Everything secret or environment-specific comes from environment variables.
See .env.example for the full list.
"""
import os
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = config('DEBUG', default=False, cast=bool)

SECRET_KEY = config('SECRET_KEY', default='')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production'
    else:
        raise RuntimeError('SECRET_KEY environment variable is required when DEBUG is off.')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://quantummanager-xmss.onrender.com',
    cast=Csv(),
)
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

# Public URL used inside emails (verification / reset links)
SITE_URL = config(
    'SITE_URL',
    default=f'https://{RENDER_EXTERNAL_HOSTNAME}' if RENDER_EXTERNAL_HOSTNAME else 'http://localhost:8000',
).rstrip('/')

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
CLOUDINARY_URL = config('CLOUDINARY_URL', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'tasks',
]
if CLOUDINARY_URL:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tasks.middleware.UserTimezoneMiddleware',
]

ROOT_URLCONF = 'djangoTodo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'djangoTodo.wsgi.application'

# ---------------------------------------------------------------------------
# Database: Postgres from DATABASE_URL in production, SQLite locally
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Time: stored in UTC, shown in each user's own timezone (see middleware)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
DEFAULT_USER_TIMEZONE = config('DEFAULT_USER_TIMEZONE', default='Africa/Lagos')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static + media files
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Render's disk is wiped on every deploy, so uploads (avatars, ringtones)
# go to Cloudinary when CLOUDINARY_URL is set.
STORAGES = {
    'default': {
        'BACKEND': (
            'cloudinary_storage.storage.RawMediaCloudinaryStorage'
            if CLOUDINARY_URL
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'

# Max upload size for custom ringtones (bytes)
MAX_TONE_UPLOAD_BYTES = 2 * 1024 * 1024

# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# ---------------------------------------------------------------------------
# Email
# Render's free plan blocks SMTP ports (25/465/587), so production email goes
# through Brevo's HTTPS API instead. Without a key, emails print to the console.
# ---------------------------------------------------------------------------
BREVO_API_KEY = config('BREVO_API_KEY', default='')
EMAIL_SEND_TIMEOUT = 10  # seconds; must stay well under gunicorn's 30s limit
DEFAULT_FROM_NAME = config('DEFAULT_FROM_NAME', default='Quantum Manager')
DEFAULT_FROM_EMAIL_ADDRESS = config('DEFAULT_FROM_EMAIL', default='quantummanagerapp@gmail.com')
DEFAULT_FROM_EMAIL = f'{DEFAULT_FROM_NAME} <{DEFAULT_FROM_EMAIL_ADDRESS}>'
EMAIL_BACKEND = (
    'tasks.email_backends.BrevoAPIBackend'
    if BREVO_API_KEY
    else 'django.core.mail.backends.console.EmailBackend'
)
# Users must verify their email before logging in only when real email works
REQUIRE_EMAIL_VERIFICATION = config('REQUIRE_EMAIL_VERIFICATION', default=bool(BREVO_API_KEY), cast=bool)

# ---------------------------------------------------------------------------
# Security (production)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
