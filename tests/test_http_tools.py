from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from toolanything.core import (
    CredentialResolver,
    HttpFieldSpec,
    HttpSourceSpec,
    RetryPolicy,
    ToolManager,
    ToolRegistry,
    build_http_input_schema,
    register_http_tool,
)
from toolanything.exceptions import ToolError


class _TestHandler(BaseHTTPRequestHandler):
    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw.decode("utf-8")) if raw else None

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/users/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "request_id": self.headers.get("X-Request-Id"),
                    }
                ).encode("utf-8")
            )
            return

        if self.path.startswith("/slow"):
            time.sleep(0.3)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        if self.path.startswith("/client-error"):
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "missing"}).encode("utf-8"))
            return

        if self.path.startswith("/server-error"):
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "boom"}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path == "/orders":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "body": self._read_json(),
                        "authorization": self.headers.get("Authorization"),
                    }
                ).encode("utf-8")
            )
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        del format, args


@pytest.fixture
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_build_http_input_schema_hides_auth_headers():
    source = HttpSourceSpec(
        name="users.fetch",
        description="取得使用者",
        method="GET",
        base_url="https://example.com",
        path="/users/{user_id}",
        path_params=(HttpFieldSpec("user_id", {"type": "string"}, required=True),),
        query_params=(HttpFieldSpec("include", {"type": "string"}),),
        body_params=(HttpFieldSpec("note", {"type": "string"}, required=True),),
        auth_ref="env:API_TOKEN",
        header_templates={"X-Request-Id": "{request_id}"},
    )

    schema = build_http_input_schema(source)

    assert schema == {
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "include": {"type": "string"},
            "body": {
                "type": "object",
                "properties": {"note": {"type": "string"}},
                "required": ["note"],
                "additionalProperties": False,
            },
        },
        "required": ["user_id", "body"],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_register_http_tool_supports_path_query_header_and_auth(http_server, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HTTP_TOOL_TOKEN", "token-123")
    registry = ToolRegistry()
    source = HttpSourceSpec(
        name="users.fetch",
        description="取得使用者",
        method="GET",
        base_url=http_server,
        path="/users/{user_id}",
        path_params=(HttpFieldSpec("user_id", {"type": "string"}, required=True),),
        query_params=(HttpFieldSpec("include", {"type": "string"}),),
        header_templates={"X-Request-Id": "{request_id}"},
        auth_ref="env:HTTP_TOOL_TOKEN",
        adapters=("mcp", "openai"),
        metadata={"category": "http"},
    )

    spec = register_http_tool(registry, source)
    result = await registry.invoke_tool_async(
        "users.fetch",
        arguments={"user_id": "42", "include": "profile", "request_id": "req-1"},
    )

    assert spec.source_type == "http"
    assert spec.func is None
    assert result == {
        "path": "/users/42?include=profile",
        "authorization": "Bearer token-123",
        "request_id": "req-1",
    }
    with pytest.raises(TypeError):
        registry.get("users.fetch")


@pytest.mark.asyncio
async def test_tool_manager_register_http_tool_supports_nested_body(http_server, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HTTP_TOOL_TOKEN", "token-456")
    manager = ToolManager(registry=ToolRegistry())
    source = HttpSourceSpec(
        name="orders.create",
        description="建立訂單",
        method="POST",
        base_url=http_server,
        path="/orders",
        body_params=(
            HttpFieldSpec("sku", {"type": "string"}, required=True),
            HttpFieldSpec("quantity", {"type": "integer"}, required=True),
        ),
        auth_ref="env:HTTP_TOOL_TOKEN",
    )

    manager.register_http_tool(source, credential_resolver=CredentialResolver())
    result = await manager.invoke(
        "orders.create",
        {"body": {"sku": "A-1", "quantity": 3}},
    )

    assert result == {
        "body": {"sku": "A-1", "quantity": 3},
        "authorization": "Bearer token-456",
    }


@pytest.mark.asyncio
async def test_http_tool_maps_timeout_to_structured_error(http_server):
    registry = ToolRegistry()
    register_http_tool(
        registry,
        HttpSourceSpec(
            name="slow.fetch",
            description="慢速端點",
            method="GET",
            base_url=http_server,
            path="/slow",
            timeout_sec=0.05,
        ),
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async("slow.fetch")

    assert exc_info.value.to_dict()["type"] == "upstream_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/client-error", 404),
        ("/server-error", 500),
    ],
)
async def test_http_tool_maps_upstream_http_errors(http_server, path: str, status: int):
    registry = ToolRegistry()
    register_http_tool(
        registry,
        HttpSourceSpec(
            name=f"error.{status}",
            description="錯誤端點",
            method="GET",
            base_url=http_server,
            path=path,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async(f"error.{status}")

    payload = exc_info.value.to_dict()
    assert payload["type"] == "upstream_http_error"
    assert payload["data"]["status"] == status
