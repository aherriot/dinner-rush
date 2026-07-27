"""Regenerates `services/kitchen/openapi.json` from the live FastAPI app.

Mirrors gateway's `manage.py spectacular` step (SPEC.md §3.5: "every service
publishes OpenAPI... CI regenerates and fails on a diff"). Run via
`make lint`, which diffs the result — a route change without a regenerated
schema fails CI.
"""

import json
from pathlib import Path

from kitchen.main import app

_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    schema = app.openapi()
    _OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
