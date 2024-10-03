export DJANGO_SETTINGS_MODULE="core.settings"
celery -A apps.tasks worker -l info -B

