from django.http import HttpRequest, JsonResponse

from dinner_rush_core.auth import build_jwk
from gateway.common.keys import get_kid, get_public_key


def jwks(request: HttpRequest) -> JsonResponse:
    """`GET /.well-known/jwks.json` (SPEC.md §6.3) — kitchen and dispatch fetch
    and cache this to verify gateway-signed tokens without a shared secret."""
    jwk = build_jwk(get_public_key(), get_kid())
    return JsonResponse({"keys": [jwk]})
