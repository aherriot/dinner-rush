"""The order state machine — SPEC.md §2, exhaustive and permissive-default-free.

`TRANSITIONS` is the only place a legal `(status, event)` pair is declared.
`apply_transition` raises `IllegalTransition` for anything not in the table —
there is deliberately no fallback branch. Guards that depend on real kitchen/
dispatch state (station free, oven slot claimed, courier available, ...)
arrive with the services that own them in Phases 4 and 7; this phase enforces
the shape of the machine, not those guards.
"""

# `place` (creation) is handled by the view that constructs the Order directly
# into `placed` — there is no prior status to transition from.
TRANSITIONS: dict[tuple[str, str], str] = {
    ("placed", "accept"): "accepted",
    ("placed", "reject"): "rejected",
    ("accepted", "enqueue"): "queued",
    ("queued", "start_prep"): "prepping",
    ("prepping", "start_bake"): "baking",
    ("baking", "finish_bake"): "boxed",
    ("boxed", "mark_ready"): "ready",
    ("ready", "assign"): "assigned",
    ("assigned", "pick_up"): "picked_up",
    ("picked_up", "depart"): "delivering",
    ("delivering", "deliver"): "delivered",
    ("delivering", "fail"): "failed",
    ("assigned", "unassign"): "ready",
    ("picked_up", "unassign"): "ready",
}

ALL_STATUSES = frozenset(
    {from_status for from_status, _ in TRANSITIONS} | set(TRANSITIONS.values())
)
ALL_EVENTS = frozenset(event for _, event in TRANSITIONS)
TERMINAL_STATUSES = frozenset({"delivered", "rejected", "failed"})


class IllegalTransition(Exception):
    pass


def apply_transition(status: str, event: str) -> str:
    """Return the resulting status for `event` fired against `status`.

    Raises `IllegalTransition` if `(status, event)` is not a legal pair.
    """
    key = (status, event)
    if key not in TRANSITIONS:
        raise IllegalTransition(f"cannot fire {event!r} from status {status!r}")
    return TRANSITIONS[key]


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES
