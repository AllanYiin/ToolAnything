from __future__ import annotations

import http.client
import json
import threading
import time

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


def _streamable_headers(*, session_id: str | None = None, protocol_version: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if session_id:
        headers[MCP_SESSION_ID_HEADER] = session_id
    if protocol_version:
        headers[MCP_PROTOCOL_VERSION_HEADER] = protocol_version
    return headers


def test_streamable_http_initialize_list_call_and_stream():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-11-25"),
        )
        resp = conn.getresponse()
        initialize_body = json.loads(resp.read())
        session_id = resp.getheader(MCP_SESSION_ID_HEADER)
        protocol_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)

        assert resp.status == 200
        assert initialize_body["result"]["protocolVersion"] == "2025-11-25"
        assert session_id
        assert protocol_version == "2025-11-25"

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            headers=_streamable_headers(
                session_id=session_id,
                protocol_version=protocol_version,
            ),
        )
        resp = conn.getresponse()
        tools_body = json.loads(resp.read())
        assert resp.status == 200
        assert any(tool["name"] == "echo" for tool in tools_body["result"]["tools"])

        conn.request("GET", "/tools")
        resp = conn.getresponse()
        direct_tools_body = json.loads(resp.read())
        assert resp.status == 200
        assert direct_tools_body["tools"] == tools_body["result"]["tools"]

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
            headers=_streamable_headers(
                session_id=session_id,
                protocol_version=protocol_version,
            ),
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
                MCP_PROTOCOL_VERSION_HEADER: protocol_version,
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


def test_streamable_http_get_replays_events_and_supports_last_event_id():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-11-25"),
        )
        resp = conn.getresponse()
        _ = json.loads(resp.read())
        session_id = resp.getheader(MCP_SESSION_ID_HEADER)
        protocol_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)

        conn.request(
            "GET",
            "/mcp",
            headers={
                "Accept": "text/event-stream",
                MCP_SESSION_ID_HEADER: session_id,
                MCP_PROTOCOL_VERSION_HEADER: protocol_version,
            },
        )
        resp = conn.getresponse()
        lines = []
        for _ in range(4):
            line = resp.fp.readline().decode("utf-8")
            lines.append(line)
            if line == "\n":
                break
        raw_stream = "".join(lines)
        assert resp.status == 200
        assert "id: 1" in raw_stream
        assert "event: ready" in raw_stream

        conn.close()

        conn = http.client.HTTPConnection("localhost", port, timeout=5)
        conn.request(
            "GET",
            "/mcp",
            headers={
                "Accept": "text/event-stream",
                "Last-Event-ID": "1",
                MCP_SESSION_ID_HEADER: session_id,
                MCP_PROTOCOL_VERSION_HEADER: protocol_version,
            },
        )
        resp = conn.getresponse()
        time.sleep(0.2)
        resp.fp.raw._sock.settimeout(0.5)
        try:
            raw_stream = resp.fp.readline().decode("utf-8")
        except OSError:
            raw_stream = ""
        assert resp.status == 200
        assert "event: ready" not in raw_stream
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_returns_202_for_notifications_and_jsonrpc_responses():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-11-25"),
        )
        resp = conn.getresponse()
        _ = json.loads(resp.read())
        session_id = resp.getheader(MCP_SESSION_ID_HEADER)
        protocol_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            headers=_streamable_headers(
                session_id=session_id,
                protocol_version=protocol_version,
            ),
        )
        resp = conn.getresponse()
        assert resp.status == 202
        assert resp.read() == b""

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 77, "result": {"ok": True}}),
            headers=_streamable_headers(
                session_id=session_id,
                protocol_version=protocol_version,
            ),
        )
        resp = conn.getresponse()
        assert resp.status == 202
        assert resp.read() == b""
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_drains_body_before_returning_404_for_wrong_post_path():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-11-25"),
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 404
        assert body["error"] == "not_found"
        assert body["transport"] == "streamable_http"
        assert body["mcp"]["endpoint"] == "/mcp"

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-11-25"),
        )
        resp = conn.getresponse()
        initialize_body = json.loads(resp.read())
        assert resp.status == 200
        assert initialize_body["id"] == 2
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_root_describes_transport_and_endpoint():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 200
        assert body["status"] == "ok"
        assert body["transport"] == "streamable_http"
        assert body["mcp"]["endpoint"] == "/mcp"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_auth_failure_session_binding_and_malformed_request():
    registry = _build_registry()
    verifier: BearerTokenVerifier = StaticTokenVerifier("good-token")
    other_verifier: BearerTokenVerifier = StaticTokenVerifier("other-token", user_id="other-user")
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
        conn.request("POST", "/mcp", body="{}", headers={"Content-Type": "application/json", "Accept": "application/json"})
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
                "Accept": "application/json",
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

    server, thread = _start_server(
        build_streamable_handler(
            registry,
            host="127.0.0.1",
            port=0,
            auth_verifier=other_verifier,
        )
    )
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)
    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer other-token",
            },
        )
        resp = conn.getresponse()
        _ = json.loads(resp.read())
        session_id = resp.getheader(MCP_SESSION_ID_HEADER)
        protocol_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

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
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer good-token",
                MCP_SESSION_ID_HEADER: session_id,
                MCP_PROTOCOL_VERSION_HEADER: protocol_version,
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 404 or resp.status == 403
        assert body["error"] in {"session_not_found", "session_owner_mismatch"}
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_rejects_protocol_mismatch_invalid_accept_and_supports_delete():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-11-25"),
        )
        resp = conn.getresponse()
        _ = json.loads(resp.read())
        session_id = resp.getheader(MCP_SESSION_ID_HEADER)
        protocol_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                MCP_SESSION_ID_HEADER: session_id,
                MCP_PROTOCOL_VERSION_HEADER: "2025-03-26",
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 400
        assert body["error"] == "protocol_version_mismatch"

        conn.request(
            "GET",
            "/mcp",
            headers={
                "Accept": "application/json",
                MCP_SESSION_ID_HEADER: session_id,
                MCP_PROTOCOL_VERSION_HEADER: protocol_version,
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 406
        assert body["error"] == "not_acceptable"

        conn.request(
            "DELETE",
            "/mcp",
            headers={
                "Accept": "application/json",
                MCP_SESSION_ID_HEADER: session_id,
                MCP_PROTOCOL_VERSION_HEADER: protocol_version,
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 200
        assert body == {"ok": True, "session_closed": True}

        conn.request(
            "POST",
            "/mcp",
            body=json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}),
            headers=_streamable_headers(
                session_id=session_id,
                protocol_version=protocol_version,
            ),
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 404
        assert body["error"] == "session_not_found"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_initialize_negotiates_supported_protocol_version():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]

    try:
        for requested_version in ("2024-11-05", "2025-06-18"):
            conn = http.client.HTTPConnection("localhost", port, timeout=5)
            try:
                conn.request(
                    "POST",
                    "/mcp",
                    body=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {"protocolVersion": requested_version},
                        }
                    ),
                    headers=_streamable_headers(protocol_version=requested_version),
                )
                resp = conn.getresponse()
                body = json.loads(resp.read())
                session_id = resp.getheader(MCP_SESSION_ID_HEADER)
                negotiated_version = resp.getheader(MCP_PROTOCOL_VERSION_HEADER)

                assert resp.status == 200
                assert body["result"]["protocolVersion"] == "2025-11-25"
                assert negotiated_version == "2025-11-25"
                assert session_id
            finally:
                conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_initialize_rejects_mismatched_protocol_sources():
    registry = _build_registry()
    server, thread = _start_server(build_streamable_handler(registry, host="127.0.0.1", port=0))
    port = server.server_address[1]
    conn = http.client.HTTPConnection("localhost", port, timeout=5)

    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05"},
                }
            ),
            headers=_streamable_headers(protocol_version="2025-06-18"),
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 400
        assert body["error"] == "protocol_version_mismatch"
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_streamable_http_legacy_sse_still_available():
    registry = _build_registry()
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
