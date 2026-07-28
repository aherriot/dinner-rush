import pytest

from simulator import cli
from simulator.config import UnknownScenarioError, UnsupportedScenarioError


def test_parse_args_defaults_scenario_to_none() -> None:
    args = cli.parse_args([])
    assert args.scenario is None


def test_parse_args_reads_the_scenario_flag() -> None:
    args = cli.parse_args(["--scenario", "friday_rush"])
    assert args.scenario == "friday_rush"


def test_unknown_scenario_exits_with_a_readable_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise(_name: str) -> None:
        raise UnknownScenarioError("no scenario named 'nope' in config.yaml")

    monkeypatch.setattr(cli.config_module, "apply_scenario_overrides", _raise)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--scenario", "nope"])

    assert exc_info.value.code == 1
    assert "nope" in capsys.readouterr().err


def test_unsupported_scenario_exits_with_a_readable_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise(_name: str) -> None:
        raise UnsupportedScenarioError("scenario 'oven_down' isn't runnable by the simulator yet")

    monkeypatch.setattr(cli.config_module, "apply_scenario_overrides", _raise)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--scenario", "oven_down"])

    assert exc_info.value.code == 1
    assert "oven_down" in capsys.readouterr().err
