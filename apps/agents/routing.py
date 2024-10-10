from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/connection_test/$', consumers.ConnectionTestConsumer.as_asgi()),
    re_path(r'ws/crew_execution/(?P<execution_id>\w+)/$', consumers.CrewExecutionConsumer.as_asgi()),
]