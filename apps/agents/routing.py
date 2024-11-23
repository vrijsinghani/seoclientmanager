from django.urls import re_path
from . import consumers
from .kanban_consumers import CrewKanbanConsumer

websocket_urlpatterns = [
    re_path(r'ws/connection_test/$', consumers.ConnectionTestConsumer.as_asgi()),
    re_path(r'ws/crew_execution/(?P<execution_id>\w+)/$', consumers.CrewExecutionConsumer.as_asgi()),
    re_path(r'ws/chat/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/crew/(?P<crew_id>\w+)/kanban/$', CrewKanbanConsumer.as_asgi()),
]