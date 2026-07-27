# Degradation — what each service does when a dependency isn't there

Companion to [ADR 0005](adr/0005-service-boundaries.md), which explains *why*
these are the answers (retry/circuit-breaker design, JWKS verification). This
is the fast-reference table: one dependency, one failure mode, one answer,
verified in `services/gateway/tests/orders/test_kitchen_client.py`.

| Dependency | State | Behaviour |
| --- | --- | --- |
| Kitchen | healthy | Normal `/capacity/quote` round trip; order accepted or rejected on the real projection. |
| Kitchen | slow (> `service_client.timeout_seconds`) | `httpx.TimeoutException` → retried (bounded, jittered) → if still failing, treated as **at capacity**: the order is rejected, not 5xx'd. |
| Kitchen | unreachable | Same as slow, faster — `ConnectError` on the first attempt. After `circuit_breaker_failure_threshold` consecutive failures, the breaker opens; every subsequent call for `circuit_breaker_reset_seconds` is refused **without touching the network**. |
| Kitchen | breaker open, recovers | The next call after the reset window is a single half-open probe. Success closes the breaker immediately. |
| Gateway's JWKS endpoint | unreachable from kitchen | Kitchen's `JWKSClient` has no key to verify against → every request 401s. Kitchen keeps cooking whatever's already queued — nothing about the tick loop or slot allocation depends on gateway — it just can't accept *new* tickets until the JWKS endpoint is reachable again. |
| A service token | expired mid-flight | Kitchen 401s; gateway does **not** retry or count it against the breaker (4xx is a real answer) — surfaces immediately as a rejected order. |
| Redis | unreachable | Out of scope for this ADR — covered by Phase 3's outbox/streams design (DECISIONS.md §0003–0004) and demoed by the `dispatch_down` scenario (config.example.yaml). |

The through-line: every row ends in **`rejected`**, never a 500. A kitchen
that's dead, slow, or unreachable is indistinguishable at the API boundary
from a kitchen that's genuinely full — both are backpressure, and
backpressure is a designed response (CLAUDE.md §2).
