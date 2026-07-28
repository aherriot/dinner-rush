"""Regenerates `services/dispatch/openapi.json` from the live FastAPI app.

Mirrors kitchen's own `scripts/export_openapi.py` (SPEC.md §3.5). Run via
`make lint`, which diffs the result.
"""

import json
from pathlib import Path

from dispatch.main import app

_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    schema = app.openapi()
    _OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
