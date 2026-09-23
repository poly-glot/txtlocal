import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from txtlocal.entrypoints.api import app, v3_app

if TYPE_CHECKING:
    from fastapi import FastAPI

FACES: dict[str, FastAPI] = {"app": app, "v3": v3_app}
SPECS = Path(__file__).resolve().parent.parent / "specs"


def render(built: FastAPI) -> str:
    return json.dumps(built.openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = (
        [
            name
            for name, built in FACES.items()
            if (SPECS / f"openapi.{name}.json").read_text() != render(built)
        ]
        if check
        else []
    )

    if check:
        for name in stale:
            sys.stdout.write(f"specs/openapi.{name}.json is stale; run scripts/export_openapi.py\n")
        return 1 if stale else 0

    for name, built in FACES.items():
        (SPECS / f"openapi.{name}.json").write_text(render(built))
        sys.stdout.write(f"wrote specs/openapi.{name}.json\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
