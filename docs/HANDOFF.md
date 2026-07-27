# Dinner Rush — implementation handoff

Prompts for handing each phase to an implementing agent. **One phase per
session.** Handing over all twelve at once produces a broad, shallow build,
which is the specific failure mode [CLAUDE.md](../CLAUDE.md) §8 warns about.

Copy the prompt, run the session, verify the acceptance criterion yourself
(§14), then move on.

---

## 1. Phase 0 — Rails

```
Read CLAUDE.md first, then PHASES.md. The documents in this directory are the
complete specification for a project called Dinner Rush.

Your scope this session is Phase 0 only.

Create the repo at ./dinner-rush/, move the specification documents into it, and
git init there. Then build Phase 0 per PHASES.md: the monorepo layout in
CLAUDE.md §3, compose.yaml with Postgres + Redis + a gateway skeleton, real
readiness healthchecks, the Makefile targets in CLAUDE.md §6, ruff + mypy strict
+ pytest, a pnpm workspace for apps/web, GitHub Actions running lint and tests,
and docs/adr/0001-why-three-services.md.

Pin exact versions and commit lockfiles. The versions in CLAUDE.md §4 are
floors, not guarantees — check current releases rather than trusting them.

Done means: from a clean clone, `make up` brings every container to healthy in
under 90 seconds, and `make lint` and `make test` are green. Run it yourself and
show me the output. Do not report done without having run it.

Do not start Phase 1. Do not write service code beyond the gateway skeleton
needed to prove compose works. If you find a genuine contradiction between the
specification documents, stop and ask rather than resolving it yourself.
```

---

## 2. Phase 1 — Design vision and design system

```
Read CLAUDE.md, then DESIGN.md in full. Phase 0 is complete.

Your scope this session is Phase 1 only — the design system.

DESIGN.md is authoritative. Implement it, do not re-derive it. Every palette
value, contrast ratio, type step, spacing step and component state is already
specified. If you find yourself choosing a colour or a size, you have skipped a
section — go back and read it.

Build: the tokens.json → tokens.css + tokens.ts pipeline (§9.1), the
primitive/semantic layer separation (§9.2), every component in §7 with all
listed states in Storybook including empty, loading and error, the stylelint and
eslint configuration in §9.3, and every check in §9.4 wired into CI.

Done means: Storybook builds with every component in light and dark; the
contrast unit test passes over tokens.json; and a commit introducing
`color: #3b82f6` into a component fails CI with a readable error. Prove that
last one by actually attempting it and showing me the failure.

No backend work. No screens — components only.
```

---

## 3. Phase 2 — The monolith that actually works

```
Read CLAUDE.md, then PHASES.md Phase 2 and SPEC.md §1.1, §2, §3.1–3.2, §5, §6.1.
Phases 0–1 are complete.

Your scope this session is Phase 2 only.

Build the Django + DRF gateway: the entities in SPEC.md §1.1, the order state
machine in §2 as an explicit FSM, the API surface in §3.1–3.2, pricing in §5,
and the roles matrix in §6.1. Cooking is instant and fake this phase. Seed menu
and customers from config.example.yaml. Build the storefront and order tracker
using the Phase 1 components only — no new components without adding them to
Storybook first.

The FSM is the part worth doing properly: transitions declared in one place,
illegal transitions raising, every row in the §2 table tested including the two
`unassign` rows. Everything else here is CRUD — build it correctly and quickly,
do not gold-plate it.

Note SPEC.md §3.1: rejection at capacity is a successful response with
`status: rejected`, not a 4xx and not a 503.

Done means: a human places an order in a browser and watches it reach delivered.
Show me the FSM test output.

Do not begin Phase 3. Do not build Celery or real cook times yet.
```

---

## 4. Phase 3 — Time, tasks and the event spine

```
Read CLAUDE.md, then PHASES.md Phase 3, DECISIONS.md §0003 and §0004, and
SPEC.md §4. Phases 0–2 are complete.

Your scope this session is Phase 3 only.

DECISIONS.md specifies this phase to the SQL. Implement it as written.

Build: Celery with staged cook times scaled by SPEED (SPEC.md §5 — durations are
stored unscaled and divided at the point of use, never stored pre-scaled); the
event envelope in DECISIONS.md §0004; the transactional outbox with the
LISTEN/NOTIFY fast path and polling fallback; Redis Streams with the topology in
§0003; consumer groups; XAUTOCLAIM recovery; the processed_event idempotency
table; and websocket fanout that resumes from last_event_id. Event payloads and
the producer/consumer matrix are in SPEC.md §4.

Redis Streams, not pub/sub. Pub/sub has no backlog and the backlog is the entire
Phase 10 recovery demo.

Done means: kill a consumer mid-stream, restart it, and show it catching up
exactly once. Refresh the browser mid-order and show the tracker resuming with
no gap. Show me both.

Do not extract any service yet.
```

---

## 5. Phase 4 — Extract `kitchen`

```
Read CLAUDE.md, then PHASES.md Phase 4, DECISIONS.md §0002, SPEC.md §1.2 and
§3.3, and the kitchen block of config.example.yaml. Phases 0–3 are complete.

Your scope this session is Phase 4 only. This is the centrepiece of the project.

Extract the kitchen into its own FastAPI + Celery service with its own Postgres
database. This must be a real refactor — code moving out of the gateway in
commits that show it — not a new directory appearing fully formed. The git
history is part of the deliverable.

Slot allocation follows DECISIONS.md §0002 exactly: Postgres is authoritative,
the claim is a single UPDATE with FOR UPDATE SKIP LOCKED, both indexes exist,
there is no lease and no Redis lock. Redis caches occupancy for reads and never
decides. Build the reaper as reconciliation against Postgres, not as lock expiry.

Kitchen's database contains no customer PII — absent, not filtered. It builds
tickets from order.accepted events and never receives a gateway DSN.

Also build: the tick loop, station contention, POST /capacity/quote as a
read-only projection that reserves nothing, backpressure per the capacity block
in config.example.yaml, and the kitchen display as a board panel.

Done means: the contention test from DECISIONS.md §0002 passes — 50 racing
claims on the last slot, exactly one winner, zero overbooking, 200 repeats in
CI. Show me that output. Then load the kitchen past capacity and show it
refusing orders at the door while continuing to cook cleanly.

Also create the branch spike/redis-lease-allocation with the deterministic
failure test described in §0002, so the failure mode we avoided is demonstrable.

Do not begin Phase 5.
```

---

## 6. Phase 5 — Boundaries done properly

```
Read CLAUDE.md, then PHASES.md Phase 5 and SPEC.md §3.5 and §6.3. Phases 0–4 are
complete.

Your scope this session is Phase 5 only.

Build: RS256 service-to-service auth with the gateway signing and publishing
JWKS, kitchen verifying against it with key caching, and the claims in SPEC.md
§6.3. Generate OpenAPI from both services and generate the typed clients into
apps/web/src/api/ — hand-written clients are a defect. Add contract tests. Give
every cross-service call an explicit timeout, a bounded retry with jitter, and a
circuit breaker. Write docs/degradation.md stating what each service does when
each dependency is unavailable, then make the code match it.

Done means: changing an endpoint produces a generated-client diff in the same
PR, and a hanging dependency degrades rather than cascading. Demonstrate the
second with a deliberately stalled kitchen.

Do not begin Phase 6.
```

---

## 7. Phase 6 — Simulator v1

```
Read CLAUDE.md §5, then PHASES.md Phase 6 and the simulator and scenarios blocks
of config.example.yaml. Phases 0–5 are complete.

Your scope this session is Phase 6 only.

Build the simulator as an ordinary API client in its own container. It
authenticates via POST /auth/token with seeded credentials, holds no service or
database credentials, imports nothing from services/, and has its own dependency
file. Enforce this in compose.yaml — no DB env vars, no privileged scope. If you
find yourself wanting to bypass the API to make it work, the API is wrong; fix
the API and tell me.

Arrivals are Poisson, not a fixed-interval loop. Use the parameters in
config.example.yaml: think times, basket weights, cancellations, repeat
customers, courier dwell times. Scenarios load from the scenarios block.

Done means: `make rush` produces genuine concurrent load through the public API
and the kitchen visibly strains. Show me the compose service definition
alongside the output, so the isolation is verifiable rather than asserted.

Do not begin Phase 7. This is a natural stopping point for the project — check
with me before continuing.
```

---

## 8. Phase 7 — Extract `dispatch`

```
Read CLAUDE.md, then PHASES.md Phase 7, SPEC.md §1.3, §3.4 and §6.2, and the
dispatch block of config.example.yaml. Phases 0–6 are complete.

Your scope this session is Phase 7 only.

Extract dispatch into its own FastAPI service with its own Postgres database.
Real refactor commits, as with Phase 4. Build Redis GEO courier positions,
nearest-available assignment within search_radius_cells, trip batching, and ETA
re-quoting. The city is the abstract 100×100 grid in config — no map tiles, no
network dependency.

Build the address_grant in SPEC.md §6.2 and all four of its tests. Case 4 —
expired grant with the trip still open — is the one people forget and the one
that proves the grant is time-boxed rather than merely lifecycle-boxed.

Courier view is a board panel, built from Phase 1 components.

Done means: couriers move, trips assign and reassign, and all four permission
tests pass. Show me the four.

Do not begin Phase 8.
```

---

## 9. Phase 8 — The Board

```
Read CLAUDE.md, then PHASES.md Phase 8, DESIGN.md §3.3 and §10, and SPEC.md
§3.1. Phases 0–7 are complete.

Your scope this session is Phase 8 only.

Build the four-panel board at the grid in DESIGN.md §10, live over websockets
with last_event_id resumption, plus the speed control and chaos buttons.

Treat this as a product, not a debug view. It is the README's first image and it
will get more attention than every backend decision combined. Use only Phase 1
components; any new component goes into Storybook with its empty, loading and
error states first. Status rendering reads the DESIGN.md §3.3 table and nothing
else — including that rejected is violet, not red, and that `late` is a modifier
that never recolours the underlying state.

It must stay legible at 40 orders/minute and when projected.

Done means: the 45-second story in PIZZA.md plays start to finish without
narration. Record it and show me.
```

---

## 10. Phase 9 — Observability and proof

```
Read CLAUDE.md, then PHASES.md Phase 9, SPEC.md §7, and the observability block
of config.example.yaml. Phases 0–8 are complete.

Your scope this session is Phase 9 only.

Build: OpenTelemetry tracing across gateway → kitchen → dispatch with the
correlation_id from the event envelope threaded through, so one order's full
fan-out is a single trace. Prometheus metrics per SPEC.md §7, a Grafana
dashboard in compose, and a k6 load test writing docs/load/latest.json.

promise_error_seconds and stream_pending are the two metrics that make our
claims falsifiable — make sure both are correct and visible on the board.

Done means: show me one order's journey as a single trace waterfall spanning
three services, and a committed load-test artifact with the command to reproduce
it printed next to the number.
```

---

## 11. Phase 10 — Chaos, recorded

```
Read CLAUDE.md, then PHASES.md Phase 10 and the scenarios block of
config.example.yaml. Phases 0–9 are complete.

Your scope this session is Phase 10 only.

Wire all five scenarios as one-click controls with the parameter deltas and
expectations already specified in config.example.yaml. Each scenario's `expect`
field is its acceptance criterion — assert it, don't just trigger it.

The one that matters is dispatch_down. Verify every line of its expectation:
gateway and kitchen stay healthy, orders keep reaching ready, stream_pending for
cg:dispatch climbs monotonically, zero 5xx on POST /orders throughout, and
XAUTOCLAIM drains the backlog on restart with every ready order assigned.

Done means: the degraded-mode recording exists and is honest. Show me the
stream_pending graph across the kill and the recovery.
```

---

## 12. Phase 11 — The interview surface

```
Read CLAUDE.md, then PHASES.md Phase 11. Phases 0–10 are complete.

Your scope this session is Phase 11 only.

Write the README leading with the rush GIF, structured as claim plus evidence —
every performance number linked to the artifact that produced it and the command
to reproduce it. Add the architecture diagram, complete the ADR set including
the decisions we would reverse, and write docs/tradeoffs.md covering what we
would do differently and what we deliberately did not build.

Verify clean-clone timing end to end.

The phrase "food delivery app" appears nowhere. The domain is the weakest part
of the pitch; the load behaviour is the pitch.
```

---

## 13. Standing additions

Append to any prompt where relevant:

- *"If you find a genuine contradiction between the specification documents,
  stop and ask rather than resolving it yourself."* — worth repeating on any
  phase touching more than one doc
- *"Do not begin Phase N+1."* — every phase
- *"Demonstrate the acceptance criterion; do not assert it."* — every phase

---

## 14. Verify between sessions

**Make it prove the criterion.** Every phase has a demonstrable "done means" — a
passing contention test, a draining backlog, a failing lint run. Ask for the
output. An agent reporting "Phase 4 complete" without showing the 200-iteration
contention test is the most likely way this goes wrong.

**Check the extractions are real.** `git log --stat` after Phases 4 and 7.
Kitchen and dispatch must appear as code *moving* out of the gateway. A service
that materialises fully formed loses the story the git history is supposed to
tell.

**Watch for drift on the three load-bearing designs.** Reject on sight:

| Drift | Why it is fatal |
| --- | --- |
| Any lock or lease in slot allocation | The centrepiece becomes the weakest claim in the project |
| Redis pub/sub anywhere in the event path | No backlog, so Phase 10 silently demonstrates nothing |
| Publishing events outside the outbox transaction | The fan-out story becomes unfalsifiable |
| Pre-scaled durations in the database | Breaks the no-virtual-clock design in a way that is painful to unwind |
| Raw hex or off-scale px in a component | The design system claim is the enforcement, not the tokens |
| Customer PII reaching kitchen's schema | Turns a structural guarantee into a filtering one |

Everything else is negotiable. These six are the project.
