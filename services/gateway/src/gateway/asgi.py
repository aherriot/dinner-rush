import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gateway.settings")

django_asgi_app = get_asgi_application()  # must run first: populates the app registry

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from gateway.eventing.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),  # type: ignore[arg-type]
    }
)
