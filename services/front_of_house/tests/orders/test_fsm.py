import itertools

import pytest

from front_of_house.orders.fsm import (
    ALL_EVENTS,
    ALL_STATUSES,
    TERMINAL_STATUSES,
    TRANSITIONS,
    IllegalTransition,
    apply_transition,
    is_terminal,
)


@pytest.mark.parametrize(
    ("status", "event", "expected"),
    [(s, e, to) for (s, e), to in TRANSITIONS.items()],
)
def test_legal_transition_reaches_the_expected_status(
    status: str, event: str, expected: str
) -> None:
    assert apply_transition(status, event) == expected


@pytest.mark.parametrize(
    ("status", "event"),
    [
        (status, event)
        for status, event in itertools.product(ALL_STATUSES, ALL_EVENTS)
        if (status, event) not in TRANSITIONS
    ],
)
def test_every_pair_not_in_the_table_raises_illegal_transition(status: str, event: str) -> None:
    with pytest.raises(IllegalTransition):
        apply_transition(status, event)


def test_unassign_returns_to_ready_from_both_assigned_and_picked_up() -> None:
    assert apply_transition("assigned", "unassign") == "ready"
    assert apply_transition("picked_up", "unassign") == "ready"


@pytest.mark.parametrize("status", sorted(TERMINAL_STATUSES))
def test_terminal_statuses_have_no_outgoing_transitions(status: str) -> None:
    outgoing = [event for (from_status, event) in TRANSITIONS if from_status == status]
    assert outgoing == []


@pytest.mark.parametrize("status", sorted(TERMINAL_STATUSES))
def test_is_terminal_true_for_delivered_rejected_failed(status: str) -> None:
    assert is_terminal(status) is True


def test_is_terminal_false_for_a_mid_flight_status() -> None:
    assert is_terminal("baking") is False


def test_unknown_status_or_event_also_raises() -> None:
    with pytest.raises(IllegalTransition):
        apply_transition("delivered", "resurrect")
