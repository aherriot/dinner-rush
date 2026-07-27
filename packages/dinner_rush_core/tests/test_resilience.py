import pytest

from dinner_rush_core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    retry_with_jitter,
)


class _Flaky:
    def __init__(self, fail_times: int, exc: type[Exception] = ConnectionError) -> None:
        self.fail_times = fail_times
        self.calls = 0
        self.exc = exc

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc("transient")
        return "ok"


def test_retry_with_jitter_succeeds_after_transient_failures() -> None:
    flaky = _Flaky(fail_times=2)
    sleeps: list[float] = []

    result = retry_with_jitter(
        flaky,
        max_attempts=3,
        base_delay_seconds=0.01,
        max_delay_seconds=1.0,
        retry_on=(ConnectionError,),
        sleep=sleeps.append,
        random_factor=lambda: 1.0,
    )

    assert result == "ok"
    assert flaky.calls == 3
    assert len(sleeps) == 2


def test_retry_with_jitter_raises_after_exhausting_attempts() -> None:
    flaky = _Flaky(fail_times=99)

    with pytest.raises(ConnectionError):
        retry_with_jitter(
            flaky,
            max_attempts=3,
            base_delay_seconds=0.01,
            max_delay_seconds=1.0,
            retry_on=(ConnectionError,),
            sleep=lambda _seconds: None,
        )
    assert flaky.calls == 3


def test_retry_with_jitter_does_not_retry_an_unlisted_exception() -> None:
    flaky = _Flaky(fail_times=99, exc=ValueError)

    with pytest.raises(ValueError):
        retry_with_jitter(
            flaky,
            max_attempts=5,
            base_delay_seconds=0.01,
            max_delay_seconds=1.0,
            retry_on=(ConnectionError,),
            sleep=lambda _seconds: None,
        )
    assert flaky.calls == 1


def test_breaker_opens_after_the_failure_threshold_and_refuses_calls() -> None:
    clock = [0.0]
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=10, clock=lambda: clock[0])
    failing = _Flaky(fail_times=99)

    for _ in range(3):
        with pytest.raises(ConnectionError):
            breaker.call(failing, retry_on=(ConnectionError,))

    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(failing, retry_on=(ConnectionError,))
    # the refused call never touched the peer
    assert failing.calls == 3


def test_breaker_half_opens_after_the_reset_timeout_and_closes_on_success() -> None:
    clock = [0.0]
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout_seconds=10, clock=lambda: clock[0])

    with pytest.raises(ConnectionError):
        breaker.call(_Flaky(fail_times=99), retry_on=(ConnectionError,))
    assert breaker.state is CircuitState.OPEN

    clock[0] = 10.0
    assert breaker.state is CircuitState.HALF_OPEN

    result = breaker.call(lambda: "recovered", retry_on=(ConnectionError,))
    assert result == "recovered"
    assert breaker.state is CircuitState.CLOSED


def test_breaker_reopens_if_the_half_open_probe_fails() -> None:
    clock = [0.0]
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout_seconds=10, clock=lambda: clock[0])

    with pytest.raises(ConnectionError):
        breaker.call(_Flaky(fail_times=99), retry_on=(ConnectionError,))

    clock[0] = 10.0
    assert breaker.state is CircuitState.HALF_OPEN

    with pytest.raises(ConnectionError):
        breaker.call(_Flaky(fail_times=99), retry_on=(ConnectionError,))
    assert breaker.state is CircuitState.OPEN

    # still within the new timeout window — stays open
    clock[0] = 15.0
    assert breaker.state is CircuitState.OPEN
