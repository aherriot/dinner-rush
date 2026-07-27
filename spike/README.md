# spike/redis-lease-allocation

The oven-slot allocation design Dinner Rush **didn't** ship — kept on this
branch, never merged to `main`, specifically so the failure mode it has can
be pointed at directly instead of just described in prose.

See [DECISIONS.md §0002](../docs/DECISIONS.md) for the real design (Postgres
as the authority, `FOR UPDATE SKIP LOCKED`, a partial unique index) and why
it replaced this one.

## The idea this spike tries

Use Redis as the allocator: `SET slot_key holder_id NX EX ttl` to claim a
slot, with the TTL as the safety net that reclaims it if the holder dies.

## Why it's wrong

A lease is a *promise* about state, held for a duration, with no
relationship to the actual state. When the lease expires — a GC pause, a
slow query, a bake that runs longer than the TTL, a stalled container — the
holder still believes it owns the slot while a second claimer legitimately
acquires the same one. Nothing in a lease-based design can detect this: both
sides did everything "correctly" by the rules of the lease. This is
Kleppmann's objection to Redlock, in its simplest possible form.

## Run it

```bash
docker compose up -d redis   # from the repo root, on any branch
uv run --with redis pytest spike/test_redis_lease_allocation.py -v
```

`test_a_stalled_holder_and_a_new_claimer_both_believe_they_own_the_slot`
is deterministic — no timing race to get unlucky on. It claims a lease with
a 1-second TTL, sleeps past it to simulate a stalled process, lets a second
claimer succeed, and asserts both calls returned `True` for the *same* slot:
two orders holding a one-slot oven, which the real design's partial unique
index (`one_slot_per_order`) makes impossible to even attempt.
