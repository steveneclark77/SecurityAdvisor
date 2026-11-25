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
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR / 'templates'], 'APP_DIRS':True,'OPTIONS':{'context_processors':['config.context_processors.app_version','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
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
NEWS_ALLOWED_HOSTS = os.getenv("NEWS_ALLOWED_HOSTS", "feeds.feedburner.com,www.bleepingcomputer.com,www.darkreading.com,www.cisa.gov,www.upguard.com,www.schneier.com,www.securityweek.com").split(",")

# Stop ingestion rather than discard historical records when a quota is reached.
NEWS_MAX_ISSUES_PER_SOURCE = int(os.getenv('NEWS_MAX_ISSUES_PER_SOURCE', '10000'))
NEWS_MAX_AUTO_VERSIONS_PER_ISSUE = int(os.getenv('NEWS_MAX_AUTO_VERSIONS_PER_ISSUE', '100'))

# Automatic feed requests require explicit deployment opt-in; manual scans remain available.
NEWS_AUTO_SCAN_ENABLED = os.getenv('NEWS_AUTO_SCAN_ENABLED', 'false').strip().lower() == 'true'

# Consistent empty choices and field-help metadata, including admin/auth forms.
FORM_RENDERER = 'library.form_rendering.AppFormRenderer'

# Review-only public-news analysis; automatic processing requires separate opt-in.
NEWS_ANALYSIS_ENABLED = os.getenv('NEWS_ANALYSIS_ENABLED','false').strip().lower() == 'true'
NEWS_ANALYSIS_MODEL = os.getenv('NEWS_ANALYSIS_MODEL','gpt-4.1-mini')
NEWS_ANALYSIS_MAX_ATTEMPTS = int(os.getenv('NEWS_ANALYSIS_MAX_ATTEMPTS','3'))
if not 1 <= NEWS_ANALYSIS_MAX_ATTEMPTS <= 10:
    raise ImproperlyConfigured('NEWS_ANALYSIS_MAX_ATTEMPTS must be between 1 and 10.')
NEWS_ANALYSIS_MAX_OUTPUT_TOKENS = 4000
NEWS_ANALYSIS_MAX_INPUT_BYTES = 60000
NEWS_ANALYSIS_PER_RUN_CENTS = int(os.getenv('NEWS_ANALYSIS_PER_RUN_CENTS','25'))
NEWS_ANALYSIS_DAILY_CENTS = int(os.getenv('NEWS_ANALYSIS_DAILY_CENTS','500'))
# Conservative configurable estimates, USD per million tokens; not billing guarantees.
NEWS_ANALYSIS_INPUT_PRICE = os.getenv('NEWS_ANALYSIS_INPUT_PRICE','1')
NEWS_ANALYSIS_OUTPUT_PRICE = os.getenv('NEWS_ANALYSIS_OUTPUT_PRICE','5')

NEWS_EMBEDDING_MODEL=os.getenv('NEWS_EMBEDDING_MODEL','text-embedding-3-small')
NEWS_EMBEDDING_PER_RUN_CENTS=int(os.getenv('NEWS_EMBEDDING_PER_RUN_CENTS','1'))
NEWS_EMBEDDING_INPUT_PRICE=os.getenv('NEWS_EMBEDDING_INPUT_PRICE','0.1')
NEWS_SLACK_DIGEST_ENABLED=os.getenv('NEWS_SLACK_DIGEST_ENABLED','false').strip().lower()=='true'
NEWS_PUBLIC_BASE_URL=os.getenv('NEWS_PUBLIC_BASE_URL','')
