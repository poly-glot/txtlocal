import importlib
import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[4] / ".github" / "workflows" / "deploy.yml"


def deployed_functions() -> list[str]:
    line = next(
        one for one in WORKFLOW.read_text().splitlines() if one.strip().startswith("FUNCTIONS:")
    )
    return line.split(":", 1)[1].split()


def module_of(function_name: str) -> str:
    return function_name.replace("-", "_")


@pytest.mark.parametrize("function_name", deployed_functions())
def test_every_deployed_function_exposes_a_callable_handler(function_name: str) -> None:
    module = importlib.import_module(f"txtlocal.entrypoints.{module_of(function_name)}")

    assert callable(getattr(module, "handler", None))


@pytest.mark.parametrize("function_name", deployed_functions())
def test_every_deployed_function_configures_telemetry_on_import(function_name: str) -> None:
    source = Path(f"src/txtlocal/entrypoints/{module_of(function_name)}.py").read_text()

    assert re.search(r"^telemetry\.configure\(\)$", source, re.MULTILINE) is not None
