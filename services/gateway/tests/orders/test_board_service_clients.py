"""`kitchen_client`'s and `dispatch_client`'s board-read functions, plus the
oven-status write path — same shape as `test_kitchen_client.py`'s coverage of
`get_capacity_quote`, extended to the endpoints Phase 8's board depends on."""

from collections.abc import Iterator
from typing import Any

import httpx
import jwt
import pytest

from dinner_rush_core.auth import build_jwk
from gateway.common.keys import get_kid, get_public_key
from gateway.orders import dispatch_client, kitchen_client


@pytest.fixture(autouse=True)
def _fresh_breakers() -> Iterator[None]:
    kitchen_client._get_breaker.cache_clear()
    dispatch_client._get_breaker.cache_clear()
    yield
    kitchen_client._get_breaker.cache_clear()
    dispatch_client._get_breaker.cache_clear()


class _FakeResponse:
    def __init__(self, status_code: int, body: Any, *, method: str = "GET") -> None:
        self.status_code = status_code
        self._body = body
        self._method = method

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request(self._method, "http://service/x")
            raise httpx.HTTPStatusError(
                "error", request=request, response=httpx.Response(self.status_code, request=request)
            )

    def json(self) -> Any:
        return self._body


class _FakeHTTP:
    def __init__(self, effects: list[Exception | _FakeResponse]) -> None:
        self.effects = list(effects)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self._next()

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self._next()

    def _next(self) -> _FakeResponse:
        effect = self.effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


def _decode(token: str) -> dict[str, Any]:
    jwk = build_jwk(get_public_key(), get_kid())
    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    result: dict[str, Any] = jwt.decode(token, key, algorithms=["RS256"])  # type: ignore[arg-type]
    return result


# -- kitchen_client.get_queue / get_ovens ------------------------------------


def test_get_queue_returns_the_ticket_list_with_a_kitchen_read_scope() -> None:
    fake = _FakeHTTP([_FakeResponse(200, [{"code": "4471"}])])

    result = kitchen_client.get_queue(correlation_id="corr-1", client=fake)

    assert result == [{"code": "4471"}]
    [call] = fake.calls
    payload = _decode(call["headers"]["Authorization"].removeprefix("Bearer "))
    assert payload["scope"] == ["kitchen:read"]
    assert payload["correlation_id"] == "corr-1"


def test_get_ovens_returns_none_when_kitchen_is_unreachable() -> None:
    cfg = kitchen_client.load_config().service_client
    fake = _FakeHTTP([httpx.ConnectError("refused")] * cfg.retry_max_attempts)

    result = kitchen_client.get_ovens(client=fake)

    assert result is None


def test_get_queue_returns_none_rather_than_raising_on_a_5xx() -> None:
    fake = _FakeHTTP([_FakeResponse(503, {"detail": "down"})])

    result = kitchen_client.get_queue(client=fake)

    assert result is None


# -- kitchen_client.set_oven_status ------------------------------------------


def test_set_oven_status_posts_with_a_kitchen_advance_scope() -> None:
    fake = _FakeHTTP([_FakeResponse(200, {"id": "oven-1", "status": "down"})])

    result = kitchen_client.set_oven_status("oven-1", "down", correlation_id="corr-2", client=fake)

    assert result == {"id": "oven-1", "status": "down"}
    [call] = fake.calls
    assert call["url"].endswith("/ovens/oven-1/status")
    payload = _decode(call["headers"]["Authorization"].removeprefix("Bearer "))
    assert payload["scope"] == ["kitchen:advance"]


def test_set_oven_status_reraises_a_404_verbatim() -> None:
    fake = _FakeHTTP([_FakeResponse(404, {"detail": "oven not found"}, method="POST")])

    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        kitchen_client.set_oven_status("missing", "down", client=fake)
    assert excinfo.value.response.status_code == 404


def test_set_oven_status_wraps_unreachability_as_kitchen_unavailable() -> None:
    cfg = kitchen_client.load_config().service_client
    fake = _FakeHTTP([httpx.ConnectError("refused")] * cfg.retry_max_attempts)

    with pytest.raises(kitchen_client.KitchenUnavailableError):
        kitchen_client.set_oven_status("oven-1", "down", client=fake)


# -- dispatch_client.get_trips / get_couriers --------------------------------


def test_get_trips_attaches_a_dispatch_read_scope() -> None:
    fake = _FakeHTTP([_FakeResponse(200, [{"code": "4471", "status": "assigned"}])])

    result = dispatch_client.get_trips(client=fake)

    assert result == [{"code": "4471", "status": "assigned"}]
    [call] = fake.calls
    payload = _decode(call["headers"]["Authorization"].removeprefix("Bearer "))
    assert payload["scope"] == ["dispatch:read"]


def test_get_couriers_returns_none_when_dispatch_is_unreachable() -> None:
    cfg = dispatch_client.load_config().service_client
    fake = _FakeHTTP([httpx.ConnectError("refused")] * cfg.retry_max_attempts)

    result = dispatch_client.get_couriers(client=fake)

    assert result is None


def test_get_backlog_attaches_a_dispatch_read_scope() -> None:
    fake = _FakeHTTP([_FakeResponse(200, {"ready_count": 4, "oldest_waiting_seconds": 512.0})])

    result = dispatch_client.get_backlog(client=fake)

    assert result == {"ready_count": 4, "oldest_waiting_seconds": 512.0}
    [call] = fake.calls
    payload = _decode(call["headers"]["Authorization"].removeprefix("Bearer "))
    assert payload["scope"] == ["dispatch:read"]


def test_get_backlog_returns_none_when_dispatch_is_unreachable() -> None:
    cfg = dispatch_client.load_config().service_client
    fake = _FakeHTTP([httpx.ConnectError("refused")] * cfg.retry_max_attempts)

    result = dispatch_client.get_backlog(client=fake)

    assert result is None


def test_dispatch_breaker_is_independent_of_kitchens() -> None:
    """The two clients each own their own `lru_cache`d breaker instance —
    dispatch being down must not trip kitchen's circuit."""
    cfg = dispatch_client.load_config().service_client
    calls_before_open = cfg.circuit_breaker_failure_threshold * cfg.retry_max_attempts
    fake = _FakeHTTP([httpx.ConnectError("refused")] * calls_before_open)
    for _ in range(cfg.circuit_breaker_failure_threshold):
        assert dispatch_client.get_trips(client=fake) is None

    kitchen_fake = _FakeHTTP([_FakeResponse(200, [])])
    assert kitchen_client.get_queue(client=kitchen_fake) == []
