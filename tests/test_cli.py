import json

from toolanything import tool
from toolanything.cli import _build_parser
from toolanything.core.registry import ToolRegistry


def test_cli_run_mcp_and_stdio_dispatch(monkeypatch):
    called = {}

    def fake_run_mcp_server(*, port: int, host: str) -> None:
        called["mcp"] = {"port": port, "host": host}

    def fake_run_stdio_server() -> None:
        called["stdio"] = True

    monkeypatch.setattr("toolanything.cli._run_mcp_server", fake_run_mcp_server)
    monkeypatch.setattr("toolanything.cli._run_stdio_server", fake_run_stdio_server)

    parser = _build_parser()

    args = parser.parse_args(["run-mcp", "--port", "1234", "--host", "127.0.0.1"])
    args.func(args)
    assert called["mcp"] == {"port": 1234, "host": "127.0.0.1"}

    args = parser.parse_args(["run-stdio"])
    args.func(args)
    assert called["stdio"] is True


def test_cli_init_claude(tmp_path):
    parser = _build_parser()
    output = tmp_path / "claude_config.json"

    args = parser.parse_args(["init-claude", "--output", str(output), "--port", "7777", "--force"])
    args.func(args)

    data = json.loads(output.read_text(encoding="utf-8"))
    entry = data["mcpServers"]["toolanything"]
    assert entry["command"] == "python"
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
        ]
    )
    args.func(args)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "existing" in data["mcpServers"]
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
