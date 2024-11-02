#!/bin/bash
PROJECT_DIR="$(dirname "$0")"  # Get project root directory
cd "$PROJECT_DIR"  # Change to project root directory
echo "Current directory: $(pwd)"

# Add the project directory to PYTHONPATH
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
export DJANGO_SETTINGS_MODULE="core.settings"

# Start Celery with nohup
mkdir -p logs pids
nohup poetry run celery -A apps.tasks worker -l info -B > ./logs/celery.log 2>&1 &
echo $! > ./pids/celery.pid