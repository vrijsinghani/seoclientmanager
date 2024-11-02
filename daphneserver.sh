#!/bin/bash
nohup poetry run python manage.py runserver 0.0.0.0:8000 > ./logs/django.log 2>&1 &
echo $! > ./pids/django.pid