import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
APP_VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY to a random secret.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'library', 'engagements', 'inventory', 'news']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[], 'APP_DIRS':True,'OPTIONS':{'context_processors':['config.context_processors.app_version','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
if os.getenv('DATABASE_ENGINE') == 'sqlite':
    DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'dev.sqlite3'}}
else:
    DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','securityadvisor'),'USER':os.getenv('POSTGRES_USER','securityadvisor'),'PASSWORD':os.getenv('POSTGRES_PASSWORD',''),'HOST':os.getenv('POSTGRES_HOST','localhost'),'PORT':os.getenv('POSTGRES_PORT','5432')}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR/'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/admin/login/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Private evidence is served only by authorized application views.
MEDIA_ROOT = BASE_DIR / "private-evidence"
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# Preserve the origin for same-origin form POSTs without disclosing invitation
# URLs in referrers to external sites. Keep public-page meta policy consistent.
SECURE_REFERRER_POLICY = 'same-origin'

# Explicit publisher allowlist: arbitrary admin URLs cannot target internal services.
NEWS_ALLOWED_HOSTS = os.getenv("NEWS_ALLOWED_HOSTS", "feeds.feedburner.com,www.bleepingcomputer.com,www.darkreading.com").split(",")
