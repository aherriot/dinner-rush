import json
from pathlib import Path

from kitchen.main import app

_CHECKED_IN_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def test_checked_in_openapi_schema_matches_the_live_app() -> None:
    """SPEC.md §3.5: "every service publishes OpenAPI... CI regenerates and
    fails on a diff." `make lint`/CI regenerate the file on disk (byte-exact,
    via `scripts/export_openapi.py`); this test catches the same drift for
    anyone running `pytest` without `make lint`, e.g. locally mid-change."""
    checked_in = json.loads(_CHECKED_IN_PATH.read_text())
    live = json.loads(json.dumps(app.openapi()))

    assert live == checked_in, (
        "services/kitchen/openapi.json is stale — "
        "run `python services/kitchen/scripts/export_openapi.py` and commit the diff"
    )
