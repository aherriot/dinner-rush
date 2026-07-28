import pytest

from simulator.config import (
    UnknownScenarioError,
    UnsupportedScenarioError,
    apply_scenario_overrides,
    load_config,
)


def test_loads_the_checked_in_example_config() -> None:
    config = load_config()

    assert config.simulator.customers.arrival == "poisson"
    assert config.simulator.customers.population == 400
    assert config.simulator.customers.basket_size_weights[1] == 0.45
    assert "friday_rush" in config.scenarios


def test_friday_rush_overrides_the_baseline_rate_and_keeps_its_duration() -> None:
    run = apply_scenario_overrides("friday_rush")

    assert run.duration_seconds == 600
    assert run.simulator.customers.baseline_rate_per_minute == 18
    assert run.simulator.customers.basket_size_weights[4] == 0.15


def test_baseline_config_is_unaffected_after_applying_a_scenario() -> None:
    apply_scenario_overrides("friday_rush")

    assert load_config().simulator.customers.baseline_rate_per_minute == 6


def test_unknown_scenario_name_raises() -> None:
    with pytest.raises(UnknownScenarioError):
        apply_scenario_overrides("not_a_real_scenario")


@pytest.mark.parametrize("name", ["oven_down", "ingredient_shortage", "courier_offline"])
def test_scenarios_the_simulator_does_not_implement_yet_are_rejected(name: str) -> None:
    with pytest.raises(UnsupportedScenarioError):
        apply_scenario_overrides(name)
