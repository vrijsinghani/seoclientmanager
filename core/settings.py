"""
Django settings for core project.

Generated by 'django-admin startproject' using Django 4.2.9.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from dotenv import load_dotenv
from str2bool       import str2bool 
import os, random, string, sys


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / '.env'
load_dotenv(dotenv_path=ENV_FILE)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = ''.join(random.choice( string.ascii_lowercase  ) for i in range( 32 ))

# Enable/Disable DEBUG Mode
DEBUG = str2bool(os.environ.get('DEBUG'))

ALLOWED_HOSTS = ['*', 'manager.neuralami.com']

# Used by DEBUG-Toolbar 
INTERNAL_IPS = [
    "127.0.0.1",
]

# Add here your deployment HOSTS
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://localhost:5085', 'http://127.0.0.1:8000', 'https://app.neuralami.com', 'http://127.0.0.1:5085', 'https://a36afd9c-6d6b-443f-af26-9f9eddab3ba1-00-12u9itbtcgrof.riker.replit.dev', 'https://manager.neuralami.com'] 


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_results',
    'debug_toolbar',
    'django_quill',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',

    'rest_framework',
    'drf_spectacular',
    'django_api_gen',
    'channels',

    'home',
    'apps.api',
    'apps.charts',
    'apps.common',
    'apps.file_manager',
    'apps.tables',
    'apps.tasks',
    'apps.users',
    'apps.seo_manager',
    'apps.crawl_website.apps.CrawlWebsiteConfig',
    'apps.agents.apps.AgentsConfig',  
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Required for allauth
    'allauth.account.middleware.AccountMiddleware',
    # Required for debug toolbar
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'apps.seo_manager.middleware.GoogleAuthMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'apps' / 'seo_manager' / 'templates',
        ],
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

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DB_ENGINE   = os.getenv('DB_ENGINE'   , None)
DB_USERNAME = os.getenv('DB_USERNAME' , None)
DB_PASS     = os.getenv('DB_PASS'     , None)
DB_HOST     = os.getenv('DB_HOST'     , None)
DB_PORT     = os.getenv('DB_PORT'     , None)
DB_NAME     = os.getenv('DB_NAME'     , None)

if DB_ENGINE and DB_NAME and DB_USERNAME:
    DATABASES = { 
      'default': {
        'ENGINE'  : 'django.db.backends.' + DB_ENGINE, 
        'NAME'    : DB_NAME,
        'USER'    : DB_USERNAME,
        'PASSWORD': DB_PASS,
        'HOST'    : DB_HOST,
        'PORT'    : DB_PORT,
        }, 
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'db.sqlite3',
        }
    }
# LiteLLM Logs Database
LITELLM_DB_ENGINE   = os.getenv('LITELLM_DB_ENGINE'   , 'postgresql')
LITELLM_DB_NAME     = os.getenv('LITELLM_DB_NAME'     , None)
LITELLM_DB_USERNAME = os.getenv('LITELLM_DB_USERNAME' , None)
LITELLM_DB_PASS     = os.getenv('LITELLM_DB_PASS'     , None)
LITELLM_DB_HOST     = os.getenv('LITELLM_DB_HOST'     , None)
LITELLM_DB_PORT     = os.getenv('LITELLM_DB_PORT'     , None)

# Add litellm_logs database if credentials are provided
if LITELLM_DB_NAME and LITELLM_DB_USERNAME:
    DATABASES['litellm_logs'] = {
        'ENGINE'  : 'django.db.backends.' + LITELLM_DB_ENGINE,
        'NAME'    : LITELLM_DB_NAME,
        'USER'    : LITELLM_DB_USERNAME,
        'PASSWORD': LITELLM_DB_PASS,
        'HOST'    : LITELLM_DB_HOST,
        'PORT'    : LITELLM_DB_PORT,
    }
STAGING_DB_ENGINE = os.getenv('STAGING_DB_ENGINE', 'postgresql')
STAGING_DB_NAME = os.getenv('STAGING_DB_NAME')
STAGING_DB_USERNAME = os.getenv('STAGING_DB_USERNAME')
STAGING_DB_PASS = os.getenv('STAGING_DB_PASS')
STAGING_DB_HOST = os.getenv('STAGING_DB_HOST')
STAGING_DB_PORT = os.getenv('STAGING_DB_PORT', '5432')

if STAGING_DB_NAME and STAGING_DB_USERNAME:
  DATABASES['staging'] = {
      'ENGINE'  : 'django.db.backends.' + STAGING_DB_ENGINE,
      'NAME'    : STAGING_DB_NAME,
      'USER'    : STAGING_DB_USERNAME,
      'PASSWORD': STAGING_DB_PASS,
      'HOST'    : STAGING_DB_HOST,
      'PORT'    : STAGING_DB_PORT,
  }
# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGES = [
    ('en', _('English (US)')),
    ('de', _('Deutsch')),
    ('it', _('Italiano')),
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR,'static'),
    os.path.join(BASE_DIR, "apps/agents/static"),

]

MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/illustration-login/'

# AllAuth
ACCOUNT_EMAIL_VERIFICATION =  os.getenv('ACCOUNT_EMAIL_VERIFICATION', 'none')
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_UNIQUE_EMAIL = True

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP':{
            'client_id': os.getenv('GOOGLE_CLIENT_ID', default=""),
            'secret': os.getenv('GOOGLE_SECRET_KEY', default=""),
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    },
    'github': {
        'APP':{
            'client_id': os.getenv('GITHUB_CLINET_ID', default=""),
            'secret': os.getenv('GITHUB_SECRET_KEY', default=""),
        }
    }
}

GOOGLE_CLIENT_SECRETS_FILE = os.getenv('GOOGLE_CLIENT_SECRETS_FILE')
GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8000/seo/google/oauth/callback/')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE', default="/secrets/service-account.json")
# ### Async Tasks (Celery) Settings ###

CELERY_SCRIPTS_DIR        = os.path.join(BASE_DIR, "tasks_scripts" )

CELERY_LOGS_URL           = "/tasks_logs/"
CELERY_LOGS_DIR           = os.path.join(BASE_DIR, "tasks_logs"    )

CELERY_BROKER_URL         = os.environ.get("CELERY_BROKER", "redis://redis:6379")
#CELERY_RESULT_BACKEND     = os.environ.get("CELERY_BROKER", "redis://redis:6379")

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT    = 30 * 60
CELERY_CACHE_BACKEND      = "django-cache"
CELERY_RESULT_BACKEND     = "django-db"
CELERY_RESULT_EXTENDED    = True
CELERY_RESULT_EXPIRES     = 60*60*24*30 # Results expire after 1 month
CELERY_ACCEPT_CONTENT     = ["json"]
CELERY_TASK_SERIALIZER    = 'json'
CELERY_RESULT_SERIALIZER  = 'json'
########################################

X_FRAME_OPTIONS = 'SAMEORIGIN'

# ### API-GENERATOR Settings ###
API_GENERATOR = {
    'sales'   : "apps.common.models.Sales",
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
########################################

MESSAGE_TAGS = {
    messages.DEBUG: 'alert-info',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger',
}

ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
DEFAULT_HTTP_PROTOCOL='https'
HTTPS=True
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

API_BASE_URL = os.environ.get('API_BASE_URL')
LITELLM_MASTER_KEY= os.environ.get('LITELLM_MASTER_KEY')
SERPAPI_API_KEY=os.environ.get('SERPAPI_API_KEY')
OPENAI_API_BASE=os.environ.get('OPENAI_API_BASE')
ALPHA_VANTAGE_API_KEY=os.environ.get('ALPHA_VANTAGE_API_KEY')
DATAFORSEO_EMAIL = os.environ.get('DATAFORSEO_EMAIL')
DATAFORSEO_PASSWORD = os.environ.get('DATAFORSEO_PASSWORD')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
PERPLEXITYAI_API_KEY = os.environ.get('PERPLEXITYAI_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
GENERAL_MODEL=os.environ.get('GENERAL_MODEL')
TEXT_MODEL=os.environ.get('TEXT_MODEL')
CODING_MODEL=os.environ.get('CODING_MODEL')
SUMMARIZER=os.environ.get('SUMMARIZER')
SUMMARIZER_MAX_TOKENS=int(os.environ.get('SUMMARIZER_MAX_TOKENS'))

EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
COMPANY_NAME = os.environ.get('COMPANY_NAME')


BROWSERLESS_API_KEY=os.environ.get('BROWSERLESS_API_KEY')
BROWSERLESS_BASE_URL=os.environ.get('BROWSERLESS_BASE_URL')
DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER')
CREWAI_DISABLE_LITELLM=os.environ.get('CREWAI_DISABLE_LITELLM')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'clean': {
            'format': '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s',
            'datefmt': '%H:%M:%S'
        },
        'minimal': {
            'format': '%(asctime)s [%(funcName)s] %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'clean',
        },
        'minimal_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'minimal',
        },
    },
    'loggers': {
        # Root logger
        '': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        # Django's built-in logging
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Celery logging
        'celery': {
            'handlers': ['minimal_console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery.worker.strategy': {
            'level': 'ERROR',
        },
        'celery.worker.consumer': {
            'level': 'ERROR',
        },
        'celery.app.trace': {
            'level': 'ERROR',
        },
        # Your apps logging
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # 'apps.agents.tools.async_crawl_website_tool': {
        #     'handlers': ['console'],
        #     'level': 'INFO',
        #     'propagate': False,
        # },
        # Specific modules you want to see more from
        'apps.seo_manager': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Silence noisy modules
        'httpx': {
            'level': 'ERROR',
        },
        'httpcore': {
            'level': 'ERROR',
        },
        'ForkPoolWorker': {
            'handlers': ['minimal_console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

TIME_ZONE = 'America/New_York'
USE_TZ = True

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('redis', 6379)],
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get("CELERY_BROKER", "redis://redis:6379/0"),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
