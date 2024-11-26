from django.urls import re_path
from .consumers import ConnectionTestConsumer, ChatConsumer
from .crew_consumers import CrewExecutionConsumer
from .kanban_consumers import CrewKanbanConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/$', ChatConsumer.as_asgi()),
    re_path(r'ws/crew/(?P<crew_id>\w+)/$', CrewExecutionConsumer.as_asgi()),
    re_path(r'ws/kanban/(?P<crew_id>\w+)/$', CrewKanbanConsumer.as_asgi()),
    re_path(r'ws/test-connection/$', ConnectionTestConsumer.as_asgi()),
]