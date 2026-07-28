"""Trip state machine — dispatch's own slice of SPEC.md §2's order FSM, plus
`unassign` (ADR 0007 §4, not in SPEC.md's original table). `apply_transition`
raises for anything not listed here; there is deliberately no permissive
default, same as `gateway.orders.fsm` and `kitchen.fsm`.
"""

TRANSITIONS: dict[tuple[str, str], str] = {
    ("assigned", "pick_up"): "picked_up",
    ("picked_up", "depart"): "delivering",
    ("delivering", "deliver"): "delivered",
    ("delivering", "fail"): "failed",
    ("assigned", "unassign"): "unassigned",
    ("picked_up", "unassign"): "unassigned",
}

TERMINAL_STATUSES = frozenset({"delivered", "failed", "unassigned"})


class IllegalTransition(Exception):
    pass


def apply_transition(status: str, event: str) -> str:
    key = (status, event)
    if key not in TRANSITIONS:
        raise IllegalTransition(f"cannot fire {event!r} from trip status {status!r}")
    return TRANSITIONS[key]


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES
