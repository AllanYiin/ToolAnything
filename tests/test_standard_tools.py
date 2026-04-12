from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from toolanything import (
    CLIExportOptions,
    StandardToolOptions,
    StandardToolRoot,
    ToolRegistry,
    build_cli_app,
    register_standard_tools,
)
from toolanything.standard_tools import StandardToolError


class _StandardToolHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/page":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><head><title>Example</title></head>"
                b"<body><p>Hello standard tools</p><a href='/next'>Next</a></body></html>"
            )
            return

        if self.path == "/redirect-private":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        del format, args


@pytest.fixture
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StandardToolHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_standard_tools_registers_safe_default_bundle(tmp_path):
    registry = ToolRegistry()
    specs = register_standard_tools(
        registry,
        StandardToolOptions(roots={"workspace": tmp_path}),
    )

    names = {spec.name for spec in specs}

    assert "standard.web.fetch" in names
    assert "standard.fs.read_text" in names
    assert "standard.data.json_parse" in names
    assert "standard.fs.write_create_only" not in names
    web_fetch = next(tool for tool in registry.to_mcp_tools() if tool["name"] == "standard.web.fetch")
    assert web_fetch["annotations"]["readOnlyHint"] is True
    assert web_fetch["annotations"]["openWorldHint"] is True


def test_standard_tools_define_stable_cli_commands(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))
    commands = {tuple(command.command_path): command for command in app.command_defs}

    assert ("standard", "web", "fetch") in commands
    assert ("standard", "fs", "read-text") in commands
    assert ("standard", "data", "json-parse") in commands
    assert commands[("standard", "web", "fetch")].metadata["cli"]["summary"].startswith("Fetch an HTTP")


def test_standard_data_tool_runs_through_cli(tmp_path, capsys: pytest.CaptureFixture[str]):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))
    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))

    exit_code = app.run(["standard", "data", "json-parse", "--text", '{"name":"tool"}', "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["tool_name"] == "standard.data.json_parse"
    assert payload["result"]["value"] == {"name": "tool"}


def test_standard_filesystem_tool_runs_through_cli(tmp_path, capsys: pytest.CaptureFixture[str]):
    (tmp_path / "note.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))
    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))

    exit_code = app.run(
        [
            "standard",
            "fs",
            "read-text",
            "--root-id",
            "workspace",
            "--relative-path",
            "note.txt",
            "--max-lines",
            "1",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["tool_name"] == "standard.fs.read_text"
    assert payload["result"]["content"] == "1|alpha"


def test_standard_write_tool_hash_guard_runs_through_cli(tmp_path, capsys: pytest.CaptureFixture[str]):
    target = tmp_path / "draft.txt"
    target.write_text("one", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(
            roots=(StandardToolRoot("workspace", tmp_path, writable=True),),
            include_write_tools=True,
        ),
    )
    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))
    expected = hashlib.sha256(b"one").hexdigest()

    exit_code = app.run(
        [
            "standard",
            "fs",
            "patch-text",
            "--root-id",
            "workspace",
            "--relative-path",
            "draft.txt",
            "--old-string",
            "one",
            "--new-string",
            "two",
            "--expected-sha256",
            expected,
            "--no-dry-run",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["tool_name"] == "standard.fs.patch_text"
    assert payload["result"]["patched"] is True
    assert target.read_text(encoding="utf-8") == "two"


@pytest.mark.asyncio
async def test_filesystem_read_blocks_traversal_and_binary(tmp_path):
    (tmp_path / "note.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    result = await registry.invoke_tool_async(
        "standard.fs.read_text",
        arguments={"root_id": "workspace", "relative_path": "note.txt", "max_lines": 1},
    )

    assert result["content"] == "1|alpha"
    assert result["line_count"] == 2
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.fs.read_text",
            arguments={"root_id": "workspace", "relative_path": "../outside.txt"},
        )
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.fs.read_text",
            arguments={"root_id": "workspace", "relative_path": "image.png"},
        )


@pytest.mark.asyncio
async def test_write_tools_are_opt_in_and_hash_guarded(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(
            roots=(StandardToolRoot("workspace", tmp_path, writable=True),),
            include_write_tools=True,
        ),
    )

    created = await registry.invoke_tool_async(
        "standard.fs.write_create_only",
        arguments={"root_id": "workspace", "relative_path": "draft.txt", "content": "one"},
    )

    assert created["created"] is True
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.fs.replace_if_match",
            arguments={
                "root_id": "workspace",
                "relative_path": "draft.txt",
                "content": "two",
                "expected_sha256": "bad",
            },
        )

    expected = hashlib.sha256(b"one").hexdigest()
    replaced = await registry.invoke_tool_async(
        "standard.fs.replace_if_match",
        arguments={
            "root_id": "workspace",
            "relative_path": "draft.txt",
            "content": "two",
            "expected_sha256": expected,
        },
    )

    assert replaced["replaced"] is True
    assert (tmp_path / "draft.txt").read_text(encoding="utf-8") == "two"


@pytest.mark.asyncio
async def test_data_tools_parse_validate_and_inspect_csv(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    parsed = await registry.invoke_tool_async(
        "standard.data.json_parse",
        arguments={"text": json.dumps({"name": "tool"})},
    )
    validation = await registry.invoke_tool_async(
        "standard.data.json_validate",
        arguments={
            "text": json.dumps({"name": "tool"}),
            "schema_text": json.dumps({"type": "object", "required": ["name"]}),
        },
    )
    csv_info = await registry.invoke_tool_async(
        "standard.data.csv_inspect",
        arguments={"text": "name,count\na,1\nb,2", "limit": 1},
    )

    assert parsed["value"] == {"name": "tool"}
    assert validation["valid"] is True
    assert csv_info["headers"] == ["name", "count"]
    assert csv_info["sample_rows"] == [["a", "1"]]
    assert csv_info["truncated"] is True


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_network_by_default_and_allows_opt_in(tmp_path, http_server):
    blocked_registry = ToolRegistry()
    register_standard_tools(blocked_registry, StandardToolOptions(roots={"workspace": tmp_path}))

    with pytest.raises(StandardToolError):
        await blocked_registry.invoke_tool_async(
            "standard.web.fetch",
            arguments={"url": f"{http_server}/page"},
        )

    allowed_registry = ToolRegistry()
    register_standard_tools(
        allowed_registry,
        StandardToolOptions(roots={"workspace": tmp_path}, allow_private_network=True),
    )
    fetched = await allowed_registry.invoke_tool_async(
        "standard.web.extract_text",
        arguments={"url": f"{http_server}/page"},
    )
    links = await allowed_registry.invoke_tool_async(
        "standard.web.extract_links",
        arguments={"url": f"{http_server}/page"},
    )

    assert fetched["title"] == "Example"
    assert "Hello standard tools" in fetched["text"]
    assert links["links"][0]["url"] == f"{http_server}/next"
