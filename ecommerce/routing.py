from django.urls import re_path
from ecommerce.consumers import RecommendationConsumer, NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/recommendations/$', RecommendationConsumer.as_asgi()),
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]
