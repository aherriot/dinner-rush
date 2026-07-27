from collections.abc import Iterator
from typing import Any

import httpx
import jwt
import pytest

from dinner_rush_core.auth import build_jwk
from gateway.common.keys import get_kid, get_public_key
from gateway.orders import kitchen_client


@pytest.fixture(autouse=True)
def _fresh_breaker() -> Iterator[None]:
    """The breaker is a process-wide `lru_cache` singleton — reset it so one
    test's failures can't leave the next test starting from an open breaker."""
    kitchen_client._get_breaker.cache_clear()
    yield
    kitchen_client._get_breaker.cache_clear()


class _FakeResponse:
    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self._body = body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://kitchen/capacity/quote")
            raise httpx.HTTPStatusError(
                "error", request=request, response=httpx.Response(self.status_code, request=request)
            )

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeHTTP:
    """Stands in for `httpx`/`httpx.Client` — `kitchen_client` only ever calls
    `.post(url, json=..., timeout=..., headers=...)` on whatever it's given."""

    def __init__(self, effects: list[Exception | _FakeResponse]) -> None:
        self.effects = list(effects)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        effect = self.effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


_ACCEPT_BODY = {"can_accept": True, "queue_depth": 1, "projected_wait_s": 120.0}


def test_attaches_a_bearer_service_token_verifiable_against_the_jwks() -> None:
    fake = _FakeHTTP([_FakeResponse(200, _ACCEPT_BODY)])

    quote = kitchen_client.get_capacity_quote(
        [{"sku": "MARG", "qty": 1}], correlation_id="corr-xyz", client=fake
    )

    assert quote.can_accept is True
    [call] = fake.calls
    token = call["headers"]["Authorization"].removeprefix("Bearer ")
    jwk = build_jwk(get_public_key(), get_kid())
    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    payload = jwt.decode(token, key, algorithms=["RS256"])  # type: ignore[arg-type]
    assert payload["role"] == "service"
    assert payload["scope"] == ["kitchen:call"]
    assert payload["correlation_id"] == "corr-xyz"


def test_retries_a_connect_error_then_succeeds() -> None:
    fake = _FakeHTTP([httpx.ConnectError("refused"), _FakeResponse(200, _ACCEPT_BODY)])

    quote = kitchen_client.get_capacity_quote([], client=fake)

    assert quote.can_accept is True
    assert len(fake.calls) == 2


def test_a_4xx_is_not_retried_and_is_treated_as_at_capacity() -> None:
    fake = _FakeHTTP([_FakeResponse(422, {"detail": "unknown sku"})])

    quote = kitchen_client.get_capacity_quote([], client=fake)

    assert quote.can_accept is False
    assert len(fake.calls) == 1


def test_exhausting_retries_is_treated_as_at_capacity() -> None:
    cfg = kitchen_client.load_config().service_client
    fake = _FakeHTTP([httpx.ConnectError("refused")] * cfg.retry_max_attempts)

    quote = kitchen_client.get_capacity_quote([], client=fake)

    assert quote.can_accept is False
    assert len(fake.calls) == cfg.retry_max_attempts


def test_breaker_opens_and_short_circuits_without_touching_the_peer() -> None:
    cfg = kitchen_client.load_config().service_client
    calls_before_open = cfg.circuit_breaker_failure_threshold * cfg.retry_max_attempts

    fake = _FakeHTTP([httpx.ConnectError("refused")] * calls_before_open)
    for _ in range(cfg.circuit_breaker_failure_threshold):
        quote = kitchen_client.get_capacity_quote([], client=fake)
        assert quote.can_accept is False
    assert len(fake.calls) == calls_before_open

    # breaker is now open — this call must not touch the peer at all
    quote = kitchen_client.get_capacity_quote([], client=fake)
    assert quote.can_accept is False
    assert len(fake.calls) == calls_before_open
