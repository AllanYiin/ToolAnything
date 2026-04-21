from __future__ import annotations

import hashlib
import io
import json
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from toolanything import (
    CLIExportOptions,
    MetadataToolPolicy,
    StandardSearchResult,
    StandardToolOptions,
    StandardToolRoot,
    ToolPolicyError,
    ToolRegistry,
    build_cli_app,
    register_standard_tools,
)
from toolanything.standard_tools import StandardToolError
from toolanything.standard_tools.filesystem import search_file_content_with_rg
from toolanything.standard_tools.safety import DomainPolicy, validate_url


class _StandardToolHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/page":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><head><title>Example</title></head>"
                b"<body><nav>Hidden navigation</nav><script>function hidden(){}</script>"
                b"<p>Hello standard tools</p><a href='/next'>Next</a></body></html>"
            )
            return

        if self.path == "/binary":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(b"\x00\x01")
            return

        if self.path == "/fake-pdf":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"%PDF-1.7\nbinary")
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
    assert "standard.fs.read_text" not in names
    assert "standard.fs.read" in names
    assert "standard.data.json_parse" in names
    assert "standard.fs.write_create_only" not in names
    assert "standard.fs.write" not in names
    web_fetch = next(tool for tool in registry.to_mcp_tools() if tool["name"] == "standard.web.fetch")
    assert web_fetch["annotations"]["readOnlyHint"] is True
    assert web_fetch["annotations"]["openWorldHint"] is True
    manifest = registry.to_tool_manifest(tags=["standard"])
    fetch_manifest = next(tool for tool in manifest if tool["name"] == "standard.web.fetch")
    assert fetch_manifest["metadata"]["scopes"] == ["net:http:get"]
    assert fetch_manifest["mcp"]["annotations"]["readOnlyHint"] is True
    assert fetch_manifest["openai"]["function"]["name"] == "standard_web_fetch"
    assert fetch_manifest["mcp"]["inputSchema"]["type"] == "object"
    assert fetch_manifest["mcp"]["outputSchema"]["type"] == "object"
    assert fetch_manifest["cli"]["commandPath"] == ["standard", "web", "fetch"]
    schema = registry.tool_manifest_schema()
    assert schema["type"] == "array"
    assert "metadata" in schema["items"]["required"]


def test_openai_export_uses_strict_schema_and_safe_names(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    fetch = next(tool for tool in registry.to_openai_tools() if tool["function"]["name"] == "standard_web_fetch")

    assert fetch["function"]["strict"] is True
    assert fetch["function"]["parameters"]["additionalProperties"] is False
    assert set(fetch["function"]["parameters"]["required"]) == set(fetch["function"]["parameters"]["properties"])


def test_standard_tool_contract_exports_openai_mcp_and_cli_metadata(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))
    spec = registry.get_tool("standard.web.fetch")

    openai = spec.to_openai()
    mcp = spec.to_mcp()
    cli = spec.to_cli()

    assert openai["function"]["name"] == "standard_web_fetch"
    assert openai["function"]["strict"] is True
    assert "inputSchema" in mcp
    assert "input_schema" not in mcp
    assert "outputSchema" in mcp
    assert mcp["annotations"]["readOnlyHint"] is True
    assert cli["commandPath"] == ["standard", "web", "fetch"]
    assert cli["arguments"]["url"]["optionStrings"] == ["--url"]


@pytest.mark.asyncio
async def test_runtime_policy_blocks_side_effecting_tools(tmp_path):
    registry = ToolRegistry(execution_policy=MetadataToolPolicy(block_side_effects=True))
    register_standard_tools(
        registry,
        StandardToolOptions(
            roots=(StandardToolRoot("workspace", tmp_path, writable=True),),
            include_write_tools=True,
        ),
    )

    with pytest.raises(ToolPolicyError):
        await registry.invoke_tool_async(
            "standard.fs.write",
            arguments={"root_id": "workspace", "relative_path": "blocked.txt", "content": "x"},
        )


def test_standard_tools_define_stable_cli_commands(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))
    commands = {tuple(command.command_path): command for command in app.command_defs}

    assert ("standard", "web", "fetch") in commands
    assert ("standard", "fs", "read-text") not in commands
    assert ("standard", "fs", "read") in commands
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


def test_standard_data_cli_reads_scalar_from_file_and_stdin(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
):
    text_file = tmp_path / "payload.json"
    text_file.write_text('{"name":"file"}', encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))
    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))

    exit_code = app.run(["standard", "data", "json-parse", "--text", f"@{text_file}", "--json"])
    file_payload = json.loads(capsys.readouterr().out)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"name":"stdin"}'))
    stdin_exit_code = app.run(["standard", "data", "json-parse", "--text", "-", "--json"])
    stdin_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert stdin_exit_code == 0
    assert file_payload["result"]["value"] == {"name": "file"}
    assert stdin_payload["result"]["value"] == {"name": "stdin"}


def test_standard_filesystem_tool_runs_through_cli(tmp_path, capsys: pytest.CaptureFixture[str]):
    (tmp_path / "note.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))
    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))

    exit_code = app.run(
        [
            "standard",
            "fs",
            "read",
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
    assert payload["tool_name"] == "standard.fs.read"
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


def test_standard_unified_patch_tool_runs_through_cli(tmp_path, capsys: pytest.CaptureFixture[str]):
    target = tmp_path / "draft.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(
            roots=(StandardToolRoot("workspace", tmp_path, writable=True),),
            include_write_tools=True,
        ),
    )
    app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))
    expected = hashlib.sha256(target.read_bytes()).hexdigest()
    patch = "--- draft.txt\n+++ draft.txt\n@@ -1,2 +1,2 @@\n one\n-two\n+three\n"

    exit_code = app.run(
        [
            "standard",
            "fs",
            "apply-unified-patch",
            "--root-id",
            "workspace",
            "--relative-path",
            "draft.txt",
            "--patch",
            patch,
            "--expected-sha256",
            expected,
            "--no-dry-run",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["tool_name"] == "standard.fs.apply_unified_patch"
    assert payload["result"]["patched"] is True
    assert target.read_text(encoding="utf-8") == "one\nthree\n"


@pytest.mark.asyncio
async def test_filesystem_read_blocks_traversal_and_binary(tmp_path):
    (tmp_path / "note.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    alias_result = await registry.invoke_tool_async(
        "standard.fs.read",
        arguments={"root_id": "workspace", "relative_path": "note.txt", "max_lines": 1},
    )

    assert alias_result["content"] == "1|alpha"
    assert alias_result["line_count"] == 2
    with pytest.raises(KeyError):
        registry.get_tool("standard.fs.read_text")
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.fs.read",
            arguments={"root_id": "workspace", "relative_path": "../outside.txt"},
        )
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.fs.read",
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

    with pytest.raises(KeyError):
        registry.get_tool("standard.fs.write_create_only")
    created = await registry.invoke_tool_async(
        "standard.fs.write",
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
async def test_standard_fs_write_creates_and_overwrites_with_hash_guard(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(
            roots=(StandardToolRoot("workspace", tmp_path, writable=True),),
            include_write_tools=True,
        ),
    )

    created = await registry.invoke_tool_async(
        "standard.fs.write",
        arguments={"root_id": "workspace", "relative_path": "draft.txt", "content": "one"},
    )

    assert created["created"] is True
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.fs.write",
            arguments={"root_id": "workspace", "relative_path": "draft.txt", "content": "two"},
        )

    expected = hashlib.sha256(b"one").hexdigest()
    replaced = await registry.invoke_tool_async(
        "standard.fs.write",
        arguments={
            "root_id": "workspace",
            "relative_path": "draft.txt",
            "content": "two",
            "expected_sha256": expected,
        },
    )

    assert replaced["created"] is False
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
    jsonl_info = await registry.invoke_tool_async(
        "standard.data.jsonl_inspect",
        arguments={"text": '{"a":1}\n{"b":2}\n{bad}', "limit": 1},
    )
    xml_info = await registry.invoke_tool_async(
        "standard.data.xml_inspect",
        arguments={"text": '<root><item id="1" /></root>'},
    )

    assert parsed["value"] == {"name": "tool"}
    assert validation["valid"] is True
    assert validation["validator"]
    assert csv_info["headers"] == ["name", "count"]
    assert csv_info["sample_rows"] == [["a", "1"]]
    assert csv_info["truncated"] is True
    assert jsonl_info["record_count"] == 2
    assert jsonl_info["errors"][0]["line"] == 3
    assert xml_info["root_tag"] == "root"


@pytest.mark.asyncio
async def test_data_tools_apply_size_limits_and_xml_hardening(tmp_path):
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}, max_read_chars=40))

    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async("standard.data.json_parse", arguments={"text": '{"value":"' + "x" * 50 + '"}'})
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async(
            "standard.data.xml_inspect",
            arguments={"text": "<!DOCTYPE root><root />"},
        )


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


@pytest.mark.asyncio
async def test_web_fetch_applies_content_policy_and_observability(tmp_path, http_server):
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(roots={"workspace": tmp_path}, allow_private_network=True),
    )

    fetched = await registry.invoke_tool_async("standard.web.fetch", arguments={"url": f"{http_server}/page"})
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async("standard.web.fetch", arguments={"url": f"{http_server}/binary"})

    assert fetched["observability"]["host"] == "127.0.0.1"
    assert fetched["observability"]["max_bytes"] == 2_000_000


@pytest.mark.asyncio
async def test_web_fetch_caps_requested_bytes_and_rejects_pdf_signature(tmp_path, http_server):
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(roots={"workspace": tmp_path}, allow_private_network=True, max_web_bytes=8),
    )

    fetched = await registry.invoke_tool_async(
        "standard.web.fetch",
        arguments={"url": f"{http_server}/page", "max_bytes": 1000},
    )
    with pytest.raises(StandardToolError):
        await registry.invoke_tool_async("standard.web.fetch", arguments={"url": f"{http_server}/fake-pdf"})

    assert fetched["observability"]["max_bytes"] == 8
    assert fetched["bytes_read"] == 8


def test_web_url_policy_blocks_metadata_hosts():
    with pytest.raises(StandardToolError):
        validate_url(
            "http://metadata.amazonaws.com/latest/meta-data/",
            allow_private_network=True,
            domain_policy=DomainPolicy(),
        )


@pytest.mark.asyncio
async def test_web_search_normalizes_standard_search_result(tmp_path):
    def provider(query: str, limit: int):
        return [
            StandardSearchResult(
                title=f"{query} title",
                url="https://example.com",
                snippet="summary",
                source="test",
            )
        ][:limit]

    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(roots={"workspace": tmp_path}, search_provider=provider),
    )

    result = await registry.invoke_tool_async("standard.web.search", arguments={"query": "tool", "limit": 1})

    assert result["results"] == [
        {
            "title": "tool title",
            "url": "https://example.com",
            "snippet": "summary",
            "source": "test",
            "published_at": "",
            "rank": 1,
        }
    ]


@pytest.mark.asyncio
async def test_web_search_uses_serpapi_env_provider_when_explicit_provider_is_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, list[str]] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "search_metadata": {"status": "Success"},
                    "organic_results": [
                        {
                            "position": 1,
                            "title": "ToolAnything",
                            "link": "https://example.com/toolanything",
                            "snippet": "Example result",
                            "source": "example.com",
                            "date": "2026-04-22",
                        }
                    ],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        del timeout
        parsed = urllib.parse.urlparse(request.full_url)
        captured.update(urllib.parse.parse_qs(parsed.query))
        return _FakeResponse()

    monkeypatch.setenv("SERPAPI_KEY", "serp-test-key")
    monkeypatch.setattr("toolanything.standard_tools.web.urllib.request.urlopen", fake_urlopen)
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    result = await registry.invoke_tool_async(
        "standard.web.search",
        arguments={"query": "toolanything", "limit": 1},
    )

    assert captured["api_key"] == ["serp-test-key"]
    assert captured["engine"] == ["google"]
    assert captured["q"] == ["toolanything"]
    assert result["results"] == [
        {
            "title": "ToolAnything",
            "url": "https://example.com/toolanything",
            "snippet": "Example result",
            "source": "example.com",
            "published_at": "2026-04-22",
            "rank": 1,
        }
    ]


@pytest.mark.asyncio
async def test_web_search_requires_provider_or_serpapi_key(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    registry = ToolRegistry()
    register_standard_tools(registry, StandardToolOptions(roots={"workspace": tmp_path}))

    with pytest.raises(StandardToolError, match="SERPAPI_KEY"):
        await registry.invoke_tool_async(
            "standard.web.search",
            arguments={"query": "toolanything", "limit": 1},
        )


@pytest.mark.asyncio
async def test_filesystem_search_respects_ignored_dirs(tmp_path):
    (tmp_path / "visible.txt").write_text("needle", encoding="utf-8")
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("needle", encoding="utf-8")
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(roots={"workspace": tmp_path}, ignored_dirs=(".hidden",)),
    )

    result = await registry.invoke_tool_async(
        "standard.fs.search",
        arguments={"root_id": "workspace", "relative_path": ".", "query": "needle", "mode": "content"},
    )

    paths = {match["relative_path"] for match in result["matches"]}
    assert "visible.txt" in paths
    assert ".hidden/secret.txt" not in paths


def test_rg_search_receives_ignored_dirs_and_file_size(monkeypatch: pytest.MonkeyPatch, tmp_path):
    commands = []

    def fake_run(command, **kwargs):
        del kwargs
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    monkeypatch.setattr("toolanything.standard_tools.filesystem.shutil.which", lambda name: "rg")
    monkeypatch.setattr("toolanything.standard_tools.filesystem.subprocess.run", fake_run)

    result = search_file_content_with_rg(
        tmp_path,
        root_path=tmp_path,
        glob="*",
        query="needle",
        limit=10,
        ignored_dirs={".hidden"},
        max_file_bytes=123,
        timeout_sec=1,
    )

    assert result == []
    assert "--max-filesize" in commands[0]
    assert "123" in commands[0]
    assert "!**/.hidden/**" in commands[0]


@pytest.mark.asyncio
async def test_optional_browser_readonly_bundle(tmp_path, http_server):
    calls = []

    def browser_provider(url: str, mode: str, limit: int):
        calls.append((url, mode, limit))
        return {"text": "dynamic text", "title": "Dynamic"}

    registry = ToolRegistry()
    specs = register_standard_tools(
        registry,
        StandardToolOptions(
            roots={"workspace": tmp_path},
            allow_private_network=True,
            include_browser_tools=True,
            browser_readonly_provider=browser_provider,
        ),
    )

    names = {spec.name for spec in specs}
    result = await registry.invoke_tool_async(
        "standard.browser.extract_text",
        arguments={"url": f"{http_server}/page"},
    )

    assert "standard.browser.extract_text" in names
    assert result["text"] == "dynamic text"
    assert calls[0][1] == "extract_text"


@pytest.mark.asyncio
async def test_web_extract_text_ignores_script_and_navigation(tmp_path, http_server):
    registry = ToolRegistry()
    register_standard_tools(
        registry,
        StandardToolOptions(roots={"workspace": tmp_path}, allow_private_network=True),
    )

    fetched = await registry.invoke_tool_async(
        "standard.web.extract_text",
        arguments={"url": f"{http_server}/page"},
    )

    assert "Hello standard tools" in fetched["text"]
    assert "function" not in fetched["text"]
