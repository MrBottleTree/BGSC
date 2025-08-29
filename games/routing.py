from django.urls import re_path
from games.consumers import LiveFeed
websocket_urlpatterns = [re_path(r"ws/live/$", LiveFeed.as_asgi())]
