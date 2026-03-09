from __future__ import annotations

import http.client
import json
import threading

from toolanything import tool
from toolanything.core.registry import ToolRegistry
from toolanything.server.mcp_auth import BearerTokenVerifier
from toolanything.server.mcp_streamable_http import (
    MCP_PROTOCOL_VERSION_HEADER,
    MCP_SESSION_ID_HEADER,
    _build_handler as build_streamable_handler,
)
from toolanything.server.mcp_tool_server import _build_handler as build_legacy_sse_handler


class StaticTokenVerifier:
    def __init__(self, accepted_token: str, user_id: str = "auth-user") -> None:
        self.accepted_token = accepted_token
        self.user_id = user_id

    def verify(self, token: str) -> str | None:
        return self.user_id if token == self.accepted_token else None


def _start_server(handler_factory):
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("localhost", 0), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @tool(name="echo", description="Echo message", registry=registry)
    def echo(message: str):
        return {"echo": message}

    return registry


def test_streamable_http_initialize_list_call_and_stream():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        initialize_body = json.loads(resp.read())
        session_id = resp.getheader(MCP_SESSION_ID_HEADER)
        protocol_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)

        assert resp.status == 200
        assert initialize_body["result"]["protocolVersion"]
        assert session_id
        assert protocol_version

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            headers={
                "Content-Type": "application/json",
                MCP_SESSION_ID_HEADER: session_id,
            },
        )
        resp = conn.getresponse()
        tools_body = json.loads(resp.read())
        assert resp.status == 200
        assert any(tool["name"] == "echo" for tool in tools_body["result"]["tools"])

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "echo", "arguments": {"message": "hi"}},
                }
            ),
            headers={
                "Content-Type": "application/json",
                MCP_SESSION_ID_HEADER: session_id,
            },
        )
        resp = conn.getresponse()
        call_body = json.loads(resp.read())
        assert resp.status == 200
        assert call_body["result"]["arguments"] == {"message": "hi"}
        assert json.loads(call_body["result"]["content"][0]["text"]) == {"echo": "hi"}

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "echo", "arguments": {"message": "stream"}},
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                MCP_SESSION_ID_HEADER: session_id,
            },
        )
        resp = conn.getresponse()
        raw_stream = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "event: message" in raw_stream
        assert "event: done" in raw_stream
        assert "\"echo\": \"stream\"" in raw_stream
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_auth_failure_and_malformed_request():
    registry = _build_registry()
    verifier: BearerTokenVerifier = StaticTokenVerifier("good-token")
    server, thread = _start_server(
        build_streamable_handler(
            registry,
            host="127.0.0.1",
            port=0,
            auth_verifier=verifier,
        )
    )
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request("POST", "/mcp", body="{}", headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 401
        assert body["error"] == "missing_bearer_token"

        conn.request(
            "POST",
            "/mcp",
            body="{bad",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer good-token",
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 400
        assert body["error"] == "invalid_json"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_get_requires_session_and_legacy_sse_still_available():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request("GET", "/mcp")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 400
        assert body["error"] == "missing_session"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    legacy_server, legacy_thread = _start_server(build_legacy_sse_handler(registry, host="127.0.0.1", port=0))
    legacy_port = legacy_server.server_address[1]
    legacy_conn = http.client.HTTPConnection("localhost", legacy_port, timeout=5)
    try:
        legacy_conn.request("GET", "/sse")
        resp = legacy_conn.getresponse()
        assert resp.status == 200
        assert resp.getheader("Content-Type") == "text/event-stream; charset=utf-8"
    finally:
        legacy_conn.close()
        legacy_server.shutdown()
        legacy_server.server_close()
        legacy_thread.join(timeout=3)
