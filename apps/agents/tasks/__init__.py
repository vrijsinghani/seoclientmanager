from celery import shared_task
from .core.crew import execute_crew

__all__ = ['execute_crew'] 