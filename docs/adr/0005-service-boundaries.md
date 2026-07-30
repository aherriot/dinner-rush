# 0005 — Boundaries done properly: service auth, timeouts, degradation

## Status

Accepted.

## Context

Phase 5 is "the difference between 'I split it into services' and 'I own the
failure modes of the split'" (PHASES.md). Two things needed deciding: how
kitchen verifies a request actually came from front-of-house now that there's a
second verifier in the system (ADR 0002 §1 deferred this), and what front-of-house's
call into kitchen does when kitchen is slow, unreachable, or refusing.

## Decisions

### 1. RS256 + JWKS, and front-of-house mints a separate, narrowly-scoped token per outbound call

Front-of-house generates an RSA keypair on first run (`front_of_house/common/keys.py`,
file-backed under a `front-of-house-keys` volume so it survives a plain restart) and
publishes the public half at `GET /.well-known/jwks.json`
(`front_of_house/common/views.py`). Kitchen fetches and caches it by `kid`
(`dinner_rush_core.auth.JWKSClient`) and verifies every request against it —
no shared secret, and kitchen never needs a copy of front-of-house's key.

Customer/staff login tokens (`accounts.views._issue_token`, still simplejwt)
and the internal service token (`front_of_house/common/service_tokens.py`, plain
PyJWT) are minted by two different code paths, not one. That's a consequence
of a real constraint, not a stylistic choice: djangorestframework-simplejwt
has no way to set a `kid` header, so a token it mints can't be looked up in a
JWKS by kid. Kitchen's endpoints therefore only accept the service token —
`role: "service"`, scoped to exactly the call being made
(`scope: ["kitchen:call"]` for `/capacity/quote`, etc.), minted fresh with a
30-second expiry for each request front-of-house makes. The 30s TTL is real
wall-clock freshness, not a simulated duration — it is deliberately **not**
divided by `SPEED` (SPEC.md §5 governs domain time, not token lifetimes).

**Consequence flagged for Phase 8**: SPEC.md §3.3 lists "front-of-house, board" as
callers of `GET /queue` and `/ovens`, and "staff" for `/tickets/{id}/advance`
— i.e., the board is supposed to call kitchen directly with a manager/kitchen
staff token, not through front-of-house. That token, minted by simplejwt, has no
`kid` and today's `JWKSClient`-based verification would reject it. Phase 8
has to either give simplejwt a `kid` header (there's a hook for a custom
`TokenBackend.encode`) or route board's kitchen reads through front-of-house as a
thin proxy. Not decided here because there's no board yet to decide it
against — deciding infrastructure for a caller that doesn't exist is exactly
the speculative-infrastructure mistake ADR 0002 §1 already named once.

### 2. Retry and circuit breaker are hand-rolled, in `dinner_rush_core.resilience`, not a dependency

`retry_with_jitter` (full-jitter exponential backoff — AWS's formulation,
`sleep(uniform(0, min(max_delay, base * 2^attempt)))`) and `CircuitBreaker`
(closed → open after N consecutive failures → half-open probe after a
timeout → closed on success / reopen on failure) are ~130 lines total,
independently tested (`test_resilience.py`), and carry no HTTP knowledge —
callers decide which exceptions count as transient. That last point is the
one that matters most in `kitchen_client.py`: only `httpx.ConnectError` and
`httpx.TimeoutException` are retried or counted against the breaker. A 4xx
from a kitchen that answered — an unknown sku, say — is a real answer, not a
fault, and both retrying it and tripping the breaker on it would be wrong.

Rejected: a dependency (`tenacity`, `pybreaker`, ...). The correctness
argument for this pair needs to fit in the space of a code review, the same
reasoning DECISIONS.md §0002 uses for hand-rolling slot allocation instead of
reaching for a queue. Two hundred lines with a real test suite is a better
signal than an opaque import for a project whose whole thesis is
demonstrating an understanding of failure handling, not delegating it.

Breaker and retry tunables live in `config.example.yaml`'s new
`service_client` block (`RootConfig.service_client`), not hardcoded, because
dispatch (Phase 7) needs the identical shape for its own outbound calls.

### 3. Degraded-mode behaviour, written down before it's demoed

The full table is [docs/degradation.md](../degradation.md) — kitchen slow,
unreachable, breaker-open-and-recovering, front-of-house's JWKS unreachable from
kitchen, and an expired service token, each with its answer. Restating only
the through-line here because it's the whole point of Phase 4 and 5 together:
every failure mode ends in **`rejected`**, never a 500. A kitchen that's dead,
slow, or unreachable is indistinguishable at the API boundary from a kitchen
that's genuinely full — both are backpressure, and backpressure is a designed
response (CLAUDE.md §2).

### 4. OpenAPI contract checks now cover kitchen too, and CI actually runs the frontend's

Kitchen publishes `services/kitchen/openapi.json` (`scripts/export_openapi.py`
dumps `app.openapi()`), checked in and drift-tested two ways: `make lint`
regenerates and diffs it (mirroring front-of-house's `manage.py spectacular` step),
and `test_openapi_contract.py` asserts the same thing so `pytest` alone
catches a stale schema without requiring `make lint` first.

Separately: `apps/web`'s `pnpm run api:check` (generated front-of-house client vs.
checked-in `schema.ts`) has existed since Phase 2 (ADR 0002 §4) but was never
actually wired into `ci.yaml` — only into the local `make lint` target. A
generated-client contract nobody's CI enforces isn't enforced. Fixed here:
`ci.yaml`'s `python` job now runs both services' OpenAPI regen-and-diff, and
the `frontend` job runs `api:check`.

## Consequences

- Phase 7 (dispatch) reuses `dinner_rush_core.resilience` and
  `dinner_rush_core.auth` as-is — a courier-facing service token is just
  another `mint_service_token(scope=[...])` call.
- Phase 8 (the board) must resolve the direct-to-kitchen staff-token gap
  flagged in Decision 1 before wiring the kitchen panel to `GET /queue` /
  `/ovens` directly.
- Phase 9's tracing should thread the service token's `correlation_id` claim
  alongside the event envelope's — they're populated from the same
  `X-Correlation-Id`, but by two different mechanisms, and a trace spanning
  front-of-house → kitchen should show both line up.

## Alternatives considered

**A single shared HS256 secret between front-of-house and kitchen, skip JWKS
entirely.** Rejected — SPEC.md §6.3 specifies RS256/JWKS explicitly, and
ADR 0002 §1 already named the reason HS256 was acceptable in Phase 2 (an
audience of one verifier, i.e. front-of-house itself) as temporary. Kitchen is a
second, independent verifier now; a shared secret between two services means
either one leaking it compromises both, and it can't be published for a third
service (dispatch, Phase 7) to independently verify against without also
handing it a secret that lets it *mint* tokens, not just check them.

**Let the board call kitchen directly this phase, ahead of Phase 8.**
Rejected — nothing calls those endpoints yet, and building the staff-token
JWKS-compatibility path (Decision 1) now, for a caller that doesn't exist,
is the same mistake ADR 0002 avoided by keeping HS256 through Phase 2.
