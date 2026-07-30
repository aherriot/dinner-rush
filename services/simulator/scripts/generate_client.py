"""Regenerates `simulator/client/models.py` from front-of-house's checked-in OpenAPI
schema (SPEC.md §3.5: "the simulator client is generated... hand-written
clients are a defect"). `make lint` reruns this and diffs the result.

Only the shapes are generated — same split as `apps/web`'s
`openapi-typescript` (generates types) + `openapi-fetch` (a thin, generic,
hand-written call layer). `simulator/client/api.py` is that layer here: it
has no endpoint-specific knowledge that could drift silently, so it stays
hand-written.
"""

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCHEMA_PATH = _REPO_ROOT / "services" / "front_of_house" / "openapi.json"
_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "src" / "simulator" / "client" / "models.py"


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(_SCHEMA_PATH),
            "--input-file-type",
            "openapi",
            "--output",
            str(_OUTPUT_PATH),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--target-python-version",
            "3.13",
            "--use-schema-description",
            "--disable-timestamp",
            "--formatters",
            "black",
            "isort",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
