"""Kitchen's slice of the order FSM (SPEC.md §2) — only the transitions
kitchen itself drives. `accepted->queued` fires synchronously when the
ticket is created (`consumers.py`); the rest run on Celery (`tasks.py`).
"""

TRANSITIONS: dict[tuple[str, str], str] = {
    ("queued", "start_prep"): "prepping",
    ("prepping", "start_bake"): "baking",
    ("baking", "finish_bake"): "boxed",
    ("boxed", "mark_ready"): "ready",
}

TERMINAL_STATUSES = frozenset({"ready"})


class IllegalTransition(Exception):
    pass


def apply_transition(status: str, event: str) -> str:
    key = (status, event)
    if key not in TRANSITIONS:
        raise IllegalTransition(f"cannot fire {event!r} from status {status!r}")
    return TRANSITIONS[key]


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES
