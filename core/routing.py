from django.urls import path
from django.utils.module_loading import import_string

websocket_urlpatterns = [
    path('ws/connection_test/', import_string('apps.agents.consumers.ConnectionTestConsumer').as_asgi()),
    path('ws/crew_execution/<str:execution_id>/', import_string('apps.agents.consumers.CrewExecutionConsumer').as_asgi()),
]