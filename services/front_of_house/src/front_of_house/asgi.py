import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "front_of_house.settings")

from front_of_house.observability import configure_web

configure_web()  # before the app registry populates, per DjangoInstrumentor's own guidance

django_asgi_app = get_asgi_application()  # must run first: populates the app registry

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from front_of_house.eventing.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),  # type: ignore[arg-type]
    }
)
