from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "examples" / "_catalog.json"

REQUIRED_FIELDS = {
    "id",
    "status",
    "level",
    "audience",
    "summary",
    "path",
    "readme",
    "run",
    "test",
    "owner",
    "introduced",
    "verified_on",
    "requires",
}
VALID_STATUSES = {"stable", "experimental", "legacy", "deprecated"}
VALID_LEVELS = {"L0", "L1", "L2", "L3", "L4"}


def _load_catalog() -> list[dict[str, object]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_examples_catalog_has_required_metadata() -> None:
    entries = _load_catalog()
    ids = [entry["id"] for entry in entries]

    assert len(ids) == len(set(ids))
    assert "quickstart" in ids
    assert "non_function_tools" in ids
    assert "vision_tools" in ids

    for entry in entries:
        missing = REQUIRED_FIELDS - set(entry)
        assert not missing, f"{entry.get('id', '<missing id>')} missing fields: {sorted(missing)}"

        assert entry["status"] in VALID_STATUSES
        assert entry["level"] in VALID_LEVELS
        assert str(entry["summary"]).strip()
        assert str(entry["run"]).strip()
        assert str(entry["test"]).strip()
        assert str(entry["owner"]).startswith("toolanything.")

        path = ROOT / str(entry["path"])
        readme = ROOT / str(entry["readme"])
        assert path.exists(), f"{entry['id']} path does not exist: {path}"
        assert readme.exists(), f"{entry['id']} README does not exist: {readme}"


def test_short_callable_examples_run_as_documented() -> None:
    weather = subprocess.run(
        [sys.executable, "examples/weather_tool/main.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "'city': 'Taipei'" in weather.stdout
    assert "weather_query" in weather.stdout

    finance = subprocess.run(
        [sys.executable, "examples/finance_tools/pipeline_demo.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "'amount': 3250.0" in finance.stdout
    assert "'last_pair': 'USD/TWD'" in finance.stdout


def test_mcp_server_demo_client_runs_cross_process() -> None:
    completed = subprocess.run(
        [sys.executable, "examples/mcp_server_demo/client.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Server is ready" in completed.stdout
    assert "echo.text" in completed.stdout
    assert "Hello MCP" in completed.stdout


def test_vision_tool_metadata_registers_without_loading_yolo_model() -> None:
    module = __import__("examples.vision_tools.server", fromlist=["registry"])
    tool_names = sorted(tool["name"] for tool in module.registry.to_mcp_tools())

    assert "vision.detect_person" in tool_names
