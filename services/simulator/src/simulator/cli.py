"""`python -m simulator.cli` — the one entrypoint.

`make sim` runs it with no arguments (baseline rate, indefinitely, until
`docker compose stop`). `make rush` passes `--scenario friday_rush` (a
named, time-boxed run — see `simulator.config.apply_scenario_overrides` for
which scenarios the simulator can run itself versus which need gateway's
admin scenario endpoint, Phase 10, or dispatch, Phase 7).
"""

import argparse
import asyncio
import contextlib
import signal
import sys
from collections.abc import Sequence

from simulator import config as config_module
from simulator import runner
from simulator.client.api import GatewayClient


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dinner Rush load simulator")
    parser.add_argument(
        "--scenario",
        default=None,
        metavar="NAME",
        help=(
            "Run a named scenario from config.yaml's `scenarios` block for its "
            "duration_seconds, then stop. Omit to run the baseline rate indefinitely."
        ),
    )
    return parser.parse_args(argv)


async def _main_async(scenario_name: str | None) -> None:
    domain_duration_seconds: float | None = None

    if scenario_name is not None:
        scenario = config_module.apply_scenario_overrides(scenario_name)
        customers_config = scenario.simulator.customers
        api_base_url = scenario.simulator.api_base_url
        domain_duration_seconds = scenario.duration_seconds
        print(f"[simulator] scenario={scenario.name!r} — {scenario.description}", flush=True)
        if scenario.expect:
            print(f"[simulator] expect: {scenario.expect}", flush=True)
    else:
        simulator_config = config_module.load_config().simulator
        customers_config = simulator_config.customers
        api_base_url = simulator_config.api_base_url
        print(
            f"[simulator] baseline — {customers_config.baseline_rate_per_minute}/min, "
            "running until stopped",
            flush=True,
        )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    client = GatewayClient(api_base_url)
    try:
        # `duration_seconds` in config.yaml is domain time like every other
        # duration there (config.example.yaml's own header comment) — divide
        # by the live SPEED at the point of use, same rule as think times and
        # dwell times, so `--speed 60` fast-forwards a scenario's real
        # wall-clock length exactly as it fast-forwards cook times.
        wall_clock_duration = None
        if domain_duration_seconds is not None:
            speed = await client.get_speed()
            wall_clock_duration = domain_duration_seconds / speed

        stats = await runner.run(
            client,
            customers_config,
            duration_seconds=wall_clock_duration,
            stop_event=stop_event,
        )
    finally:
        await client.aclose()

    print(f"[simulator] final: {stats.snapshot()}", flush=True)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        asyncio.run(_main_async(args.scenario))
    except config_module.UnknownScenarioError as exc:
        print(f"[simulator] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except config_module.UnsupportedScenarioError as exc:
        print(f"[simulator] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
