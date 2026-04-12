from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolanything import ToolRegistry, build_cli_app, export_cli_project, load_cli_project, tool
from toolanything.cli import _build_parser, run_exported_cli
from toolanything.cli_export import CLICommandOverride, CLIExportOptions
from toolanything.cli_export.exceptions import (
    CLIArgumentValidationError,
    CLINamingConflictError,
    CLIProjectConfigError,
)
from toolanything.cli_export.naming import build_command_definitions, tool_name_to_command_path
from toolanything.core.models import ToolSpec


def test_cli_project_config_round_trip(tmp_path: Path):
    registry = ToolRegistry()

    @tool(name="weather.query", description="查天氣", registry=registry)
    def weather(city: str) -> dict:
        return {"city": city}

    config_path = tmp_path / "toolanything.cli.json"
    options = CLIExportOptions(app_name="mytools", default_output_mode="json")
    export_cli_project(registry, str(config_path), options, module="tests.fixtures.sample_tools")

    loaded = load_cli_project(str(config_path))
    assert loaded.app_name == "mytools"
    assert loaded.tools == ["weather.query"]
    assert loaded.module == "tests.fixtures.sample_tools"
    assert loaded.state == "generated"


def test_cli_project_config_reports_json_error(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(CLIProjectConfigError) as exc_info:
        load_cli_project(str(path))

    assert "line" in str(exc_info.value)


def test_command_naming_and_conflict_detection():
    assert tool_name_to_command_path("weather.query") == ["weather", "query"]
    registry = ToolRegistry()

    @tool(name="weather.query", description="查天氣", registry=registry)
    def weather(city: str) -> dict:
        return {"city": city}

    @tool(name="weather-query", description="另一個工具", registry=registry)
    def weather_query(city: str) -> dict:
        return {"city": city}

    options = CLIExportOptions(app_name="mytools", command_naming="flat")
    with pytest.raises(CLINamingConflictError):
        build_command_definitions(registry.list(), options=options)


def test_cli_app_runs_via_registry(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    registry = ToolRegistry()

    @tool(name="math.add", description="相加", registry=registry)
    def add(a: int, b: int = 1) -> int:
        return a + b

    calls: list[tuple[str, dict[str, int]]] = []

    async def fake_invoke_tool_async(name: str, **kwargs):
        calls.append((name, kwargs["arguments"]))
        return 7

    monkeypatch.setattr(registry, "invoke_tool_async", fake_invoke_tool_async)
    app = build_cli_app(registry, CLIExportOptions(app_name="mytools"))

    exit_code = app.run(["math", "add", "--a", "3", "--b", "4", "--json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [("math.add", {"a": 3, "b": 4})]
    payload = json.loads(output)
    assert payload["tool_name"] == "math.add"
    assert payload["result"] == 7


def test_cli_app_validates_path_and_renders_artifact(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    registry = ToolRegistry()
    input_file = tmp_path / "note.txt"
    input_file.write_text("preview me", encoding="utf-8")

    @tool(name="doc.echo", description="回傳檔案路徑", registry=registry)
    def echo(file_path: str) -> str:
        return file_path

    app = build_cli_app(registry, CLIExportOptions(app_name="mytools"))
    exit_code = app.run(["doc", "echo", "--file-path", str(input_file)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Artifacts:" in output
    assert str(input_file) in output


def test_cli_app_validates_aspect_ratio(capsys: pytest.CaptureFixture[str]):
    registry = ToolRegistry()

    def resize(width: int, height: int) -> dict:
        return {"width": width, "height": height}

    spec = ToolSpec.from_function(
        resize,
        name="image.resize",
        description="調整尺寸",
        metadata={
            "cli": {
                "aspect_ratio": {
                    "width": "width",
                    "height": "height",
                    "original_width": 16,
                    "original_height": 9,
                }
            }
        },
    )
    registry.register(spec)
    app = build_cli_app(registry, CLIExportOptions(app_name="mytools"))

    exit_code = app.run(["image", "resize", "--width", "800", "--height", "800"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "aspect ratio" in output


def test_cli_app_parses_nullable_scalar_arguments(capsys: pytest.CaptureFixture[str]):
    registry = ToolRegistry()

    @tool(name="image.resize", description="調整尺寸", registry=registry)
    def resize(target_width: int | None = None, target_height: int | None = None) -> dict:
        return {"target_width": target_width, "target_height": target_height}

    app = build_cli_app(registry, CLIExportOptions(app_name="mytools"))

    exit_code = app.run(["image", "resize", "--target-width", "80", "--json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["result"]["target_width"] == 80
    assert payload["result"]["target_height"] is None


def test_cli_export_and_run_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config_path = tmp_path / "toolanything.cli.json"
    launcher_path = tmp_path / "mytools.py"
    parser = _build_parser()

    args = parser.parse_args(
        [
            "cli",
            "export",
            "--module",
            "tests.fixtures.sample_tools",
            "--config",
            str(config_path),
            "--app-name",
            "mytools",
            "--launcher",
            str(launcher_path),
        ]
    )
    args.func(args)
    capsys.readouterr()

    assert config_path.exists()
    assert launcher_path.exists()

    exit_code = run_exported_cli(str(config_path), ["math", "add", "--a", "2", "--b", "3", "--json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert json.loads(output)["result"] == 5


def test_cli_command_override_changes_path():
    registry = ToolRegistry()

    @tool(name="weather.query", description="查天氣", registry=registry)
    def weather(city: str) -> dict:
        return {"city": city}

    app = build_cli_app(
        registry,
        CLIExportOptions(app_name="mytools"),
        project_config=load_cli_project_from_override("mytools"),
    )
    assert app.command_defs[0].command_path == ["wx", "current"]


def test_tool_decorator_cli_command_changes_path():
    registry = ToolRegistry()

    @tool(
        name="weather.query",
        description="查天氣",
        registry=registry,
        cli_command="wx current",
    )
    def weather(city: str) -> dict:
        return {"city": city}

    app = build_cli_app(registry, CLIExportOptions(app_name="mytools"))
    assert app.command_defs[0].command_path == ["wx", "current"]


def test_cli_argument_metadata_can_disable_path_like_inference(capsys: pytest.CaptureFixture[str]):
    registry = ToolRegistry()

    def read_virtual(relative_path: str) -> dict:
        return {"relative_path": relative_path}

    registry.register(
        ToolSpec.from_function(
            read_virtual,
            name="virtual.read",
            description="讀取虛擬 root 內的相對路徑",
            metadata={"cli": {"arguments": {"relative_path": {"path_like": False}}}},
        )
    )
    app = build_cli_app(registry, CLIExportOptions(app_name="mytools"))

    exit_code = app.run(["virtual", "read", "--relative-path", "missing.txt", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["result"] == {"relative_path": "missing.txt"}


def test_project_config_override_precedes_tool_cli_command():
    registry = ToolRegistry()

    @tool(
        name="weather.query",
        description="查天氣",
        registry=registry,
        cli_command="weather now",
    )
    def weather(city: str) -> dict:
        return {"city": city}

    app = build_cli_app(
        registry,
        CLIExportOptions(app_name="mytools"),
        project_config=load_cli_project_from_override("mytools"),
    )
    assert app.command_defs[0].command_path == ["wx", "current"]


def load_cli_project_from_override(app_name: str):
    from toolanything.cli_export.types import CLIProjectConfig

    return CLIProjectConfig(
        version="1",
        app_name=app_name,
        tools=["weather.query"],
        command_overrides={
            "weather.query": CLICommandOverride(command_path=["wx", "current"])
        },
    )
