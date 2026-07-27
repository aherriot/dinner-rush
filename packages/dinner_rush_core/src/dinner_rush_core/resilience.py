"""Bounded retry with jitter, and a small in-process circuit breaker.

PHASES.md Phase 5: "every cross-service call gets an explicit timeout,
bounded retry with jitter, and a circuit breaker." Hand-rolled rather than a
dependency — the whole point of this pair is a correctness argument you can
read in thirty lines, not a black box.

Neither one is aware of HTTP; callers decide which exceptions count as a
transient failure worth retrying/tripping the breaker on (a 4xx from a
reachable, healthy peer is not one of them).
"""

import random
import threading
import time
from collections.abc import Callable
from enum import Enum


def retry_with_jitter[T](
    fn: Callable[[], T],
    *,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    retry_on: tuple[type[Exception], ...],
    sleep: Callable[[float], None] = time.sleep,
    random_factor: Callable[[], float] = random.random,
) -> T:
    """Full-jitter exponential backoff (AWS's "full jitter" — uniform(0, cap)),
    so N concurrent callers retrying together don't retry in lockstep."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except retry_on:
            if attempt == max_attempts:
                raise
            cap = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            sleep(cap * random_factor())
    raise AssertionError("unreachable — loop always returns or raises on last attempt")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """The breaker is open — the call was refused without touching the peer."""


class CircuitBreaker:
    """Closed → Open after `failure_threshold` consecutive failures. Open →
    Half-open after `reset_timeout_seconds`, admitting exactly one probe call.
    That probe succeeding closes the breaker; failing reopens it and restarts
    the timeout.

    Thread-safe (Django/FastAPI workers call this from multiple threads);
    state is per-process, which is the right scope for a laptop demo — there
    is no shared breaker state to coordinate across processes.
    """

    def __init__(
        self,
        *,
        failure_threshold: int,
        reset_timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._effective_state()

    def _effective_state(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and (self._clock() - self._opened_at) >= self._reset_timeout_seconds
        ):
            return CircuitState.HALF_OPEN
        return self._state

    def call[T](self, fn: Callable[[], T], *, retry_on: tuple[type[Exception], ...]) -> T:
        with self._lock:
            state = self._effective_state()
            if state is CircuitState.OPEN:
                raise CircuitBreakerOpenError("circuit is open")
            if state is CircuitState.HALF_OPEN:
                self._state = CircuitState.HALF_OPEN

        try:
            result = fn()
        except retry_on:
            with self._lock:
                self._consecutive_failures += 1
                if (
                    self._state is CircuitState.HALF_OPEN
                    or self._consecutive_failures >= self._failure_threshold
                ):
                    self._state = CircuitState.OPEN
                    self._opened_at = self._clock()
            raise
        else:
            with self._lock:
                self._state = CircuitState.CLOSED
                self._consecutive_failures = 0
                self._opened_at = None
            return result
