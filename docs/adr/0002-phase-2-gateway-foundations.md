# 0002 — Phase 2 gateway foundations

## Status

Accepted.

## Context

Phase 2 builds the Django monolith — menu, customers, orders, pricing, roles,
admin — with the order FSM as the one piece worth doing properly (PHASES.md
Phase 2, CLAUDE.md §2). Three things needed a decision that will visibly
change in later phases and are worth writing down now rather than
reconstructing later.

## Decisions

### 1. HS256 JWT now, RS256 + JWKS in Phase 5

`POST /auth/token` issues HS256-signed JWTs verified only by the gateway
itself. SPEC.md §6.3 specifies RS256 with a published JWKS so `kitchen` and
`dispatch` can verify gateway-issued tokens without a shared secret — but
those services don't exist yet. Standing up asymmetric signing and a JWKS
endpoint for an audience of one verifier is speculative infrastructure with
nothing to verify it. HS256 is swapped for RS256 in Phase 5, when there's a
second verifier to prove it against.

### 2. Customers authenticate by email only; staff by username + password

SPEC.md §1.1's `customer` table has no credentials column, deliberately —
this phase has no signup flow, and the CRUD half is explicitly not where
effort should go (CLAUDE.md §2). Customers log in with just their seeded
email; staff (`kitchen`/`manager`) authenticate against
`django.contrib.auth.User` with a real password, since that path is reused
by Django's auth machinery for free. `TokenView` picks the branch based on
whether the request body has `password`, which also means the request body
for `/auth/token` doesn't have a single documented shape — its OpenAPI
schema (`TokenRequestSerializer`) is intentionally a schema-only superset,
not a serializer that ever validates.

### 3. Fake progression is a background thread, not Celery

An accepted order needs to visibly reach `delivered` for the demo (PHASES.md
Phase 2's "done means"), but there is no kitchen service, no Celery, and no
event spine until Phases 3 and 4. `gateway.orders.progression` stands in with
a plain `threading.Thread` that walks the FSM on fixed short delays and
writes `OrderStatusEvent` rows directly — no outbox, no Redis Streams. This
is explicitly throwaway: Phase 3 replaces it with Celery tasks driven by real
per-item cook times, publishing through the outbox instead of writing to this
table directly. Two consequences worth flagging for later phases:

- Delays are still divided by the runtime `SPEED` value at the point of use
  (`accounts.speed.get_speed()`), because the no-virtual-clock rule
  (SPEC.md §5) is a project-wide invariant, not a Phase 3+ one.
- The thread is per-order and un-supervised — correct for a single dev-server
  process on a laptop, and not something to carry into the Celery-backed
  replacement.

### 4. The API client is generated starting this phase, not deferred to Phase 5

SPEC.md §3.5 requires generated clients "from Phase 5" implicitly (contract
tests land there), but hand-writing a fetch client now and replacing it with
a generated one later means doing the work twice and shipping the exact
drift bug (SPEC §3.5) the generated-client rule exists to prevent. Instead:
`drf-spectacular` exposes `/api/schema` and a checked-in
`services/gateway/openapi.json`; `openapi-typescript` generates
`apps/web/src/api/schema.ts` from that file (not a live server), and
`openapi-fetch` provides the thin typed call layer. `pnpm run api:check`
mirrors the existing `tokens:check` pattern — regenerate, diff, fail on
drift.

### 5. CORS is a local-dev allowlist, not a wildcard

The storefront (`:5173`) calls the gateway (`:8000`) cross-origin in dev.
`django-cors-headers` is configured with an explicit origin allowlist
(`http://localhost:5173`) rather than `CORS_ALLOW_ALL_ORIGINS` — this project
is never hosted (CLAUDE.md preamble), so there's no production origin to
generalize for, and an explicit allowlist costs nothing.

## Consequences

- Phase 5 must revisit: JWT signing (HS256 → RS256/JWKS) and the token
  request/response schema once cross-service verification is real.
- Phase 3 must revisit: `orders/progression.py` is deleted wholesale, not
  extended — `OrderStatusEvent` as a status-history table may still be worth
  keeping for `GET /orders/{code}/timeline`, but it stops being the mechanism
  that drives state transitions.
- The order tracker polls (`OrderTracker.tsx`, ~1.5s) instead of using a
  websocket — an explicit placeholder for Phase 3's fanout with
  last-event-id resume, called out in the component's own docstring so it
  isn't mistaken for a considered choice.

## Alternatives considered

**Skip generated clients until Phase 5, hand-write the fetch calls now.**
Rejected — this project's own standing rule (SPEC.md §3.5) is that
hand-written clients are a defect because drift is exactly what the project
claims to manage; doing it twice costs more than doing it once, correctly,
from Phase 2.

**Give `Customer` a password field to unify the auth code path.** Rejected —
it would contradict SPEC.md §1.1's domain model for no real benefit in a
phase that has no signup flow to protect anyway.
