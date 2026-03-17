import importlib
import json

import pytest

from toolanything import tool
from toolanything.cli import _build_parser
from toolanything.core.registry import ToolRegistry
from toolanything.runtime.serve import load_tool_module


def test_cli_run_mcp_and_stdio_dispatch(monkeypatch):
    called = {}

    def fake_run_mcp_server(*, port: int, host: str) -> None:
        called["mcp"] = {"port": port, "host": host}

    def fake_run_stdio_server() -> None:
        called["stdio"] = True

    def fake_run_streamable_http_server(*, port: int, host: str) -> None:
        called["streamable_http"] = {"port": port, "host": host}

    monkeypatch.setattr("toolanything.cli._run_mcp_server", fake_run_mcp_server)
    monkeypatch.setattr("toolanything.cli._run_stdio_server", fake_run_stdio_server)
    monkeypatch.setattr("toolanything.cli._run_streamable_http_server", fake_run_streamable_http_server)

    parser = _build_parser()

    args = parser.parse_args(["run-mcp", "--port", "1234", "--host", "127.0.0.1"])
    args.func(args)
    assert called["mcp"] == {"port": 1234, "host": "127.0.0.1"}

    args = parser.parse_args(["run-stdio"])
    args.func(args)
    assert called["stdio"] is True

    args = parser.parse_args(["run-streamable-http", "--port", "1235", "--host", "127.0.0.1"])
    args.func(args)
    assert called["streamable_http"] == {"port": 1235, "host": "127.0.0.1"}


def test_cli_inspect_dispatch(monkeypatch):
    called = {}

    def fake_run_inspector_ui(*, host: str, port: int, timeout: float, no_open: bool) -> None:
        called["inspect"] = {
            "host": host,
            "port": port,
            "timeout": timeout,
            "no_open": no_open,
        }

    monkeypatch.setattr("toolanything.cli._run_inspector_ui", fake_run_inspector_ui)
    parser = _build_parser()

    args = parser.parse_args(["inspect", "--port", "9061", "--host", "127.0.0.1", "--timeout", "5", "--no-open"])
    args.func(args)

    assert called["inspect"] == {
        "host": "127.0.0.1",
        "port": 9061,
        "timeout": 5.0,
        "no_open": True,
    }


def test_cli_serve_passes_transport_flags(monkeypatch):
    called = {}

    def fake_serve_module(
        *,
        module: str,
        host: str,
        port: int,
        stdio: bool,
        streamable_http: bool,
        legacy_http: bool,
    ) -> None:
        called["serve"] = {
            "module": module,
            "host": host,
            "port": port,
            "stdio": stdio,
            "streamable_http": streamable_http,
            "legacy_http": legacy_http,
        }

    monkeypatch.setattr("toolanything.cli._serve_module", fake_serve_module)
    parser = _build_parser()

    args = parser.parse_args(["serve", "examples/quickstart/tools.py"])
    args.func(args)
    assert called["serve"] == {
        "module": "examples/quickstart/tools.py",
        "host": "127.0.0.1",
        "port": 9090,
        "stdio": False,
        "streamable_http": False,
        "legacy_http": False,
    }

    args = parser.parse_args(["serve", "examples/quickstart/tools.py", "--legacy-http"])
    args.func(args)
    assert called["serve"]["legacy_http"] is True
    assert called["serve"]["stdio"] is False
    assert called["serve"]["streamable_http"] is False


def test_cli_doctor_defaults_to_http():
    parser = _build_parser()
    args = parser.parse_args(["doctor"])
    assert args.mode == "http"


def test_cli_init_claude(tmp_path):
    parser = _build_parser()
    output = tmp_path / "claude_config.json"

    args = parser.parse_args(
        [
            "init-claude",
            "--output",
            str(output),
            "--port",
            "7777",
            "--module",
            "examples/opencv_mcp_web/server.py",
            "--force",
        ]
    )
    args.func(args)

    data = json.loads(output.read_text(encoding="utf-8"))
    entry = data["mcpServers"]["toolanything"]
    assert entry["command"] == "python"
    assert entry["args"][3] == "examples/opencv_mcp_web/server.py"
    assert "--port" in entry["args"]
    assert entry["args"][-1] == "7777"


def test_cli_install_claude_merges_existing(tmp_path):
    parser = _build_parser()
    config_path = tmp_path / "config.json"
    existing = {"mcpServers": {"existing": {"command": "python", "args": ["--old"]}}}
    config_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    args = parser.parse_args(
        [
            "install-claude",
            "--config",
            str(config_path),
            "--port",
            "8081",
            "--name",
            "custom",
            "--module",
            "examples/opencv_mcp_web/server.py",
        ]
    )
    args.func(args)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "existing" in data["mcpServers"]
    assert data["mcpServers"]["custom"]["args"][3] == "examples/opencv_mcp_web/server.py"
    assert data["mcpServers"]["custom"]["args"][-1] == "8081"


def test_cli_search_arguments_forwarding(monkeypatch):
    captured = {}

    def fake_run_search(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("toolanything.cli._run_search", fake_run_search)
    parser = _build_parser()

    args = parser.parse_args(
        [
            "search",
            "--query",
            "math",
            "--tags",
            "alpha",
            "beta",
            "--prefix",
            "tool",
            "--top-k",
            "5",
            "--disable-failure-sort",
            "--max-cost",
            "1.5",
            "--latency-budget-ms",
            "250",
            "--allow-side-effects",
            "--category",
            "io,admin",
            "--category",
            "analysis",
        ]
    )
    args.func(args)

    assert captured == {
        "query": "math",
        "tags": ["alpha", "beta"],
        "prefix": "tool",
        "top_k": 5,
        "sort_by_failure": False,
        "max_cost": 1.5,
        "latency_budget_ms": 250,
        "allow_side_effects": True,
        "categories": ["io", "admin", "analysis"],
    }


def test_cli_search_uses_registry(tmp_path, monkeypatch, capsys):
    """確保搜尋命令會呼叫實際 searcher 並輸出結果。"""

    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()

    @tool(name="demo.echo", description="回聲", registry=registry)
    def echo(message: str):
        return message

    def fake_global_instance():
        return registry

    monkeypatch.setattr("toolanything.core.registry.ToolRegistry.global_instance", staticmethod(fake_global_instance))

    parser = _build_parser()
    args = parser.parse_args(["search", "--query", "echo"])
    args.func(args)

    output = capsys.readouterr().out
    assert "demo.echo" in output
    assert "failure_score" in output
    assert "latency_hint_ms" in output


def test_load_tool_module_accepts_external_file_path(tmp_path, monkeypatch):
    registry = ToolRegistry()
    monkeypatch.setattr(
        "toolanything.core.registry.ToolRegistry.global_instance",
        staticmethod(lambda: registry),
    )

    script_path = tmp_path / "external_tool.py"
    script_path.write_text(
        "from toolanything import tool\n\n"
        "@tool(name='external.echo', description='外部工具')\n"
        "def external_echo(message: str) -> str:\n"
        "    return message\n",
        encoding="utf-8",
    )

    load_tool_module(str(script_path))

    names = [spec.name for spec in registry.list()]
    assert "external.echo" in names


def test_load_tool_module_resolves_relative_file_path_from_repo_root(tmp_path, monkeypatch):
    runtime_serve = importlib.import_module("toolanything.runtime.serve")
    registry = ToolRegistry()
    monkeypatch.setattr(
        "toolanything.core.registry.ToolRegistry.global_instance",
        staticmethod(lambda: registry),
    )

    repo_root = tmp_path / "repo"
    script_path = repo_root / "examples" / "opencv_mcp_web" / "server.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(
        "from toolanything import tool\n\n"
        "@tool(name='repo.echo', description='Repo 工具')\n"
        "def repo_echo(message: str) -> str:\n"
        "    return message\n",
        encoding="utf-8",
    )

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    monkeypatch.chdir(outside_dir)
    monkeypatch.setattr(runtime_serve, "_REPO_ROOT", repo_root)

    load_tool_module("examples/opencv_mcp_web/server.py")

    names = [spec.name for spec in registry.list()]
    assert "repo.echo" in names


def test_load_tool_module_reports_clear_error_for_missing_pathlike_input(tmp_path, monkeypatch):
    runtime_serve = importlib.import_module("toolanything.runtime.serve")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_serve, "_REPO_ROOT", tmp_path / "repo")

    with pytest.raises(FileNotFoundError) as exc_info:
        load_tool_module("examples/opencv_mcp_web/server.py")

    message = str(exc_info.value)
    assert "examples/opencv_mcp_web/server.py" in message
    assert str(tmp_path) in message
    assert "repo root" in message
