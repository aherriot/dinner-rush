import pytest
from sqlalchemy.orm import Session

from kitchen.cli import run_seed
from kitchen.models import Oven, OvenSlot, Station


@pytest.fixture(autouse=True)
def _menu_config(monkeypatch: pytest.MonkeyPatch) -> None:
    import kitchen.cli as cli_module
    from dinner_rush_core.config import CapacityConfig, OvenConfig, StationConfig

    class _FakeKitchenConfig:
        ovens = [OvenConfig(name="Oven 1", slot_count=3), OvenConfig(name="Oven 2", slot_count=2)]
        stations = [StationConfig(name="Prep", kind="prep", capacity=3)]
        tick_interval_seconds = 1
        slot_reaper_interval_seconds = 5
        slot_reaper_grace_seconds = 30
        capacity = CapacityConfig(
            max_queue_depth=40,
            max_projected_wait_seconds=2700,
            promise_buffer_seconds=180,
            reject_when_all_ovens_down=True,
        )

    class _FakeConfig:
        kitchen = _FakeKitchenConfig()

    monkeypatch.setattr(cli_module, "load_config", lambda: _FakeConfig())


def test_seed_creates_ovens_with_slots_and_stations(session: Session) -> None:
    run_seed()

    ovens = session.query(Oven).order_by(Oven.name).all()
    assert [o.name for o in ovens] == ["Oven 1", "Oven 2"]

    slots = session.query(OvenSlot).all()
    assert len(slots) == 5  # 3 + 2, the exact bug this test guards against

    for oven in ovens:
        oven_slots = [s for s in slots if s.oven_id == oven.id]
        assert len(oven_slots) == oven.slot_count
        assert {s.slot_index for s in oven_slots} == set(range(oven.slot_count))

    assert session.query(Station).count() == 1


def test_seed_is_a_no_op_if_ovens_already_exist(session: Session) -> None:
    run_seed()
    run_seed()

    assert session.query(Oven).count() == 2
    assert session.query(OvenSlot).count() == 5
