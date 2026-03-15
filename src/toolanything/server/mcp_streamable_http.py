"""MCP Streamable HTTP transport.

This is the recommended HTTP transport. The existing SSE transport remains as a
legacy compatibility layer.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from ..core.registry import ToolRegistry
from ..core.result_serializer import ResultSerializer
from ..core.security_manager import SecurityManager
from ..protocol.mcp_jsonrpc import MCPProtocolCoreImpl, MCPRequestContext
from .mcp_auth import BearerTokenVerifier
from .mcp_runtime import build_protocol_dependencies

MCP_PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"
MCP_SESSION_ID_HEADER = "Mcp-Session-Id"
_STREAM_HEARTBEAT_SEC = 15.0
_STREAM_HISTORY_LIMIT = 256


def _streamable_http_endpoints() -> Dict[str, str]:
    return {
        "health": "/health",
        "tools": "/tools",
        "mcp": "/mcp",
    }


def _streamable_http_status_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "transport": "streamable_http",
        "mcp": {
            "transport": "streamable_http",
            "endpoint": "/mcp",
        },
        "endpoints": _streamable_http_endpoints(),
    }


def _streamable_http_not_found_payload(path: str) -> Dict[str, Any]:
    return {
        "error": "not_found",
        "transport": "streamable_http",
        "path": path,
        "hint": "Streamable HTTP MCP requests must use /mcp.",
        "mcp": {
            "transport": "streamable_http",
            "endpoint": "/mcp",
        },
    }


@dataclass(frozen=True, slots=True)
class StreamEvent:
    event_id: int
    name: str
    payload: Dict[str, Any]


@dataclass(slots=True)
class StreamableSession:
    user_id: str
    protocol_version: str
    history_limit: int = _STREAM_HISTORY_LIMIT
    last_seen_monotonic: float = field(default_factory=time.monotonic)
    events: list[StreamEvent] = field(default_factory=list)
    next_event_id: int = 0
    closed: bool = False
    condition: threading.Condition = field(default_factory=threading.Condition)

    def touch(self) -> None:
        with self.condition:
            self.last_seen_monotonic = time.monotonic()

    def append_event(self, name: str, payload: Dict[str, Any]) -> StreamEvent:
        with self.condition:
            self.next_event_id += 1
            event = StreamEvent(self.next_event_id, name, payload)
            self.events.append(event)
            if len(self.events) > self.history_limit:
                self.events = self.events[-self.history_limit :]
            self.last_seen_monotonic = time.monotonic()
            self.condition.notify_all()
            return event

    def replay_events_after(self, after_event_id: int) -> list[StreamEvent]:
        with self.condition:
            if self.events and after_event_id < self.events[0].event_id - 1:
                raise ValueError("event_history_unavailable")
            return [event for event in self.events if event.event_id > after_event_id]

    def wait_for_events(self, after_event_id: int, *, timeout_sec: float) -> bool:
        deadline = time.monotonic() + timeout_sec
        with self.condition:
            while True:
                has_new_event = any(event.event_id > after_event_id for event in self.events)
                if has_new_event or self.closed:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(timeout=remaining)

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.last_seen_monotonic = time.monotonic()
            self.condition.notify_all()


def _build_allowed_origins(host: str, port: int) -> set[str]:
    configured = os.getenv("TOOLANYTHING_ALLOWED_ORIGINS")
    if configured:
        return {item.strip() for item in configured.split(",") if item.strip()}

    allowed = {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        f"https://127.0.0.1:{port}",
        f"https://localhost:{port}",
    }
    if host not in {"0.0.0.0", "::", ""}:
        allowed.add(f"http://{host}:{port}")
        allowed.add(f"https://{host}:{port}")
    return allowed


def _send_cors_headers(handler: BaseHTTPRequestHandler, *, allowed_origins: set[str]) -> None:
    origin = handler.headers.get("Origin")
    if origin and ("*" in allowed_origins or origin in allowed_origins):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
    handler.send_header(
        "Access-Control-Allow-Headers",
        (
            "Accept, Content-Type, Authorization, Last-Event-ID, "
            f"{MCP_PROTOCOL_VERSION_HEADER}, {MCP_SESSION_ID_HEADER}"
        ),
    )
    handler.send_header("Access-Control-Max-Age", "600")


def _json_response(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    payload: Dict[str, Any],
    *,
    allowed_origins: set[str],
    protocol_version: str | None = None,
    session_id: str | None = None,
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    _send_cors_headers(handler, allowed_origins=allowed_origins)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    if protocol_version:
        handler.send_header(MCP_PROTOCOL_VERSION_HEADER, protocol_version)
    if session_id:
        handler.send_header(MCP_SESSION_ID_HEADER, session_id)
    handler.end_headers()
    handler.wfile.write(body)


def _empty_response(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    *,
    allowed_origins: set[str],
    protocol_version: str | None = None,
    session_id: str | None = None,
) -> None:
    handler.send_response(status_code)
    _send_cors_headers(handler, allowed_origins=allowed_origins)
    handler.send_header("Content-Length", "0")
    if protocol_version:
        handler.send_header(MCP_PROTOCOL_VERSION_HEADER, protocol_version)
    if session_id:
        handler.send_header(MCP_SESSION_ID_HEADER, session_id)
    handler.end_headers()


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any] | None:
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        return None

    raw_body = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _drain_request_body(handler: BaseHTTPRequestHandler) -> None:
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        return
    if content_length > 0:
        handler.rfile.read(content_length)


def _send_sse_headers(
    handler: BaseHTTPRequestHandler,
    *,
    allowed_origins: set[str],
    protocol_version: str | None = None,
    session_id: str | None = None,
) -> None:
    handler.send_response(200)
    _send_cors_headers(handler, allowed_origins=allowed_origins)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    if protocol_version:
        handler.send_header(MCP_PROTOCOL_VERSION_HEADER, protocol_version)
    if session_id:
        handler.send_header(MCP_SESSION_ID_HEADER, session_id)
    handler.end_headers()


def _write_sse_event(
    handler: BaseHTTPRequestHandler,
    event: str,
    data: Dict[str, Any],
    *,
    event_id: int | None = None,
) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    if event_id is not None:
        handler.wfile.write(f"id: {event_id}\n".encode("utf-8"))
    handler.wfile.write(f"event: {event}\n".encode("utf-8"))
    for line in payload.splitlines():
        handler.wfile.write(f"data: {line}\n".encode("utf-8"))
    handler.wfile.write(b"\n")
    handler.wfile.flush()


def _parse_accept_header(header_value: str | None) -> set[str]:
    if not header_value:
        return set()
    tokens: set[str] = set()
    for part in header_value.split(","):
        token = part.split(";", 1)[0].strip().lower()
        if token:
            tokens.add(token)
    return tokens


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    prefix = "Bearer "
    if header_value.startswith(prefix):
        return header_value[len(prefix) :].strip() or None
    return None


def _parse_last_event_id(header_value: str | None) -> int | None:
    if header_value is None or header_value.strip() == "":
        return None
    try:
        value = int(header_value)
    except ValueError as exc:
        raise ValueError("invalid_last_event_id") from exc
    if value < 0:
        raise ValueError("invalid_last_event_id")
    return value


def _build_handler(
    registry: ToolRegistry,
    *,
    host: str,
    port: int,
    serializer: ResultSerializer | None = None,
    security_manager: SecurityManager | None = None,
    auth_verifier: BearerTokenVerifier | None = None,
) -> type[BaseHTTPRequestHandler]:
    active_serializer = serializer or ResultSerializer()
    active_security_manager = security_manager or SecurityManager()
    allowed_origins = _build_allowed_origins(host, port)
    protocol_core = MCPProtocolCoreImpl()
    adapter, _, _, protocol_deps = build_protocol_dependencies(
        registry,
        serializer=active_serializer,
        security_manager=active_security_manager,
    )
    protocol_version = adapter.PROTOCOL_VERSION
    sessions: dict[str, StreamableSession] = {}
    sessions_lock = threading.Lock()

    class MCPStreamableHTTPHandler(BaseHTTPRequestHandler):
        server_version = "ToolAnythingMCPStreamable/0.1"
        protocol_version = "HTTP/1.1"

        def _origin_allowed(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin or "*" in allowed_origins:
                return True
            return origin in allowed_origins

        def _reject_disallowed_origin(self) -> None:
            _json_response(
                self,
                403,
                {"error": "origin_not_allowed"},
                allowed_origins=allowed_origins,
                protocol_version=protocol_version,
            )

        def _require_auth(self) -> str | None:
            if auth_verifier is None:
                return "default"

            token = _extract_bearer_token(self.headers.get("Authorization"))
            if token is None:
                _json_response(
                    self,
                    401,
                    {"error": "missing_bearer_token"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return None

            user_id = auth_verifier.verify(token)
            if user_id is None:
                _json_response(
                    self,
                    401,
                    {"error": "invalid_bearer_token"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return None
            return user_id

        def _get_session(self, session_id: str) -> StreamableSession | None:
            with sessions_lock:
                return sessions.get(session_id)

        def _store_session(self, session_id: str, session: StreamableSession) -> None:
            with sessions_lock:
                sessions[session_id] = session

        def _remove_session(self, session_id: str) -> StreamableSession | None:
            with sessions_lock:
                return sessions.pop(session_id, None)

        def _resolve_session(
            self,
            user_id: str,
        ) -> tuple[str | None, StreamableSession | None]:
            session_id = self.headers.get(MCP_SESSION_ID_HEADER)
            if not session_id:
                return None, None

            session = self._get_session(session_id)
            if session is None:
                raise KeyError("session_not_found")

            if auth_verifier is not None and session.user_id != user_id:
                raise PermissionError("session_owner_mismatch")

            session.touch()
            return session_id, session

        def _protocol_error(
            self,
            error: str,
            *,
            status_code: int = 400,
            session_id: str | None = None,
        ) -> None:
            _json_response(
                self,
                status_code,
                {"error": error},
                allowed_origins=allowed_origins,
                protocol_version=protocol_version,
                session_id=session_id,
            )

        def _validate_protocol_version(
            self,
            *,
            session_id: str | None,
            method: str | None,
            payload: Dict[str, Any] | None = None,
        ) -> str | None:
            header_version = self.headers.get(MCP_PROTOCOL_VERSION_HEADER)

            if method == "initialize":
                params = (payload or {}).get("params", {}) or {}
                requested_version = params.get("protocolVersion")
                if (
                    header_version
                    and requested_version
                    and header_version != requested_version
                ):
                    self._protocol_error("protocol_version_mismatch")
                    return None
                return protocol_version

            if session_id is None:
                if header_version and header_version != protocol_version:
                    self._protocol_error("unsupported_protocol_version")
                    return None
                return header_version or protocol_version

            session = self._get_session(session_id)
            if session is None:
                self._protocol_error("session_not_found", status_code=404)
                return None

            effective_version = header_version or session.protocol_version
            if effective_version != session.protocol_version:
                self._protocol_error("protocol_version_mismatch", session_id=session_id)
                return None

            return effective_version

        def _validate_post_accept(self) -> str | None:
            accepts = _parse_accept_header(self.headers.get("Accept"))
            if not accepts:
                self._protocol_error("not_acceptable", status_code=406)
                return None

            accepts_json = "*/*" in accepts or "application/json" in accepts
            accepts_stream = "text/event-stream" in accepts
            if not accepts_json and not accepts_stream:
                self._protocol_error("not_acceptable", status_code=406)
                return None
            if accepts_stream and not accepts_json:
                return "stream"
            return "json"

        def _validate_get_accept(self) -> bool:
            accepts = _parse_accept_header(self.headers.get("Accept"))
            if "*/*" in accepts or "text/event-stream" in accepts:
                return True
            self._protocol_error("not_acceptable", status_code=406)
            return False

        def _validate_json_content_type(self) -> bool:
            content_type = (self.headers.get("Content-Type") or "").lower()
            if not content_type:
                self._protocol_error("unsupported_media_type", status_code=415)
                return False
            if "application/json" not in content_type:
                self._protocol_error("unsupported_media_type", status_code=415)
                return False
            return True

        def _write_stream_events(
            self,
            *,
            session: StreamableSession,
            session_id: str,
            effective_version: str,
            after_event_id: int,
        ) -> None:
            _send_sse_headers(
                self,
                allowed_origins=allowed_origins,
                protocol_version=effective_version,
                session_id=session_id,
            )

            last_sent_event_id = after_event_id
            while True:
                for event in session.replay_events_after(last_sent_event_id):
                    _write_sse_event(
                        self,
                        event.name,
                        event.payload,
                        event_id=event.event_id,
                    )
                    last_sent_event_id = event.event_id

                if session.closed:
                    self.close_connection = True
                    return

                has_new_event = session.wait_for_events(
                    last_sent_event_id,
                    timeout_sec=_STREAM_HEARTBEAT_SEC,
                )
                if has_new_event:
                    continue

                _write_sse_event(self, "ping", {"ts": time.time()})

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._origin_allowed():
                self._reject_disallowed_origin()
                return
            self.send_response(204)
            _send_cors_headers(self, allowed_origins=allowed_origins)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if not self._origin_allowed():
                self._reject_disallowed_origin()
                return

            if self.path in {"/", "/health"}:
                _json_response(
                    self,
                    200,
                    _streamable_http_status_payload(),
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            if self.path == "/tools":
                _json_response(
                    self,
                    200,
                    {"tools": registry.to_mcp_tools()},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            if self.path != "/mcp":
                _json_response(
                    self,
                    404,
                    _streamable_http_not_found_payload(self.path),
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            if not self._validate_get_accept():
                return

            user_id = self._require_auth()
            if user_id is None:
                return

            try:
                session_id, session = self._resolve_session(user_id)
            except KeyError:
                self._protocol_error("session_not_found", status_code=404)
                return
            except PermissionError:
                self._protocol_error("session_owner_mismatch", status_code=403)
                return

            if session_id is None or session is None:
                self._protocol_error("missing_session")
                return

            effective_version = self._validate_protocol_version(
                session_id=session_id,
                method=None,
            )
            if effective_version is None:
                return

            try:
                last_event_id = _parse_last_event_id(self.headers.get("Last-Event-ID"))
            except ValueError:
                self._protocol_error("invalid_last_event_id")
                return

            after_event_id = last_event_id or 0
            try:
                session.replay_events_after(after_event_id)
            except ValueError:
                self._protocol_error(
                    "event_history_unavailable",
                    status_code=409,
                    session_id=session_id,
                )
                return

            try:
                self._write_stream_events(
                    session=session,
                    session_id=session_id,
                    effective_version=effective_version,
                    after_event_id=after_event_id,
                )
            except BrokenPipeError:
                self.close_connection = True
            except ConnectionResetError:
                self.close_connection = True

        def do_POST(self) -> None:  # noqa: N802
            if not self._origin_allowed():
                _drain_request_body(self)
                self._reject_disallowed_origin()
                return

            if self.path != "/mcp":
                _drain_request_body(self)
                _json_response(
                    self,
                    404,
                    _streamable_http_not_found_payload(self.path),
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            response_mode = self._validate_post_accept()
            if response_mode is None:
                _drain_request_body(self)
                return

            if not self._validate_json_content_type():
                _drain_request_body(self)
                return

            user_id = self._require_auth()
            if user_id is None:
                _drain_request_body(self)
                return

            payload = _read_json(self)
            if payload is None:
                _json_response(
                    self,
                    400,
                    {"error": "invalid_json"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            method = payload.get("method")
            is_jsonrpc_response = "method" not in payload and "id" in payload

            try:
                session_id, session = self._resolve_session(user_id)
            except KeyError:
                _json_response(
                    self,
                    404,
                    {"error": "session_not_found"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return
            except PermissionError:
                _json_response(
                    self,
                    403,
                    {"error": "session_owner_mismatch"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            if method == "initialize" and session_id is None:
                effective_version = self._validate_protocol_version(
                    session_id=None,
                    method=method,
                    payload=payload,
                )
                if effective_version is None:
                    return

                session_id = uuid.uuid4().hex
                session = StreamableSession(
                    user_id=user_id,
                    protocol_version=effective_version,
                )
                session.append_event(
                    "ready",
                    {
                        "session_id": session_id,
                        "transport": "streamable_http",
                    },
                )
                self._store_session(session_id, session)
            else:
                effective_version = self._validate_protocol_version(
                    session_id=session_id,
                    method=method,
                    payload=payload,
                )
                if effective_version is None:
                    return

            if is_jsonrpc_response:
                _empty_response(
                    self,
                    202,
                    allowed_origins=allowed_origins,
                    protocol_version=effective_version,
                    session_id=session_id,
                )
                return

            context = MCPRequestContext(
                user_id=user_id,
                session_id=session_id,
                transport="streamable_http",
            )
            response = protocol_core.handle(
                payload,
                context=context,
                deps=protocol_deps,
            )

            is_notification = payload.get("id") is None or response is None
            if is_notification:
                _empty_response(
                    self,
                    202,
                    allowed_origins=allowed_origins,
                    protocol_version=effective_version,
                    session_id=session_id,
                )
                return

            if response_mode == "stream":
                _send_sse_headers(
                    self,
                    allowed_origins=allowed_origins,
                    protocol_version=effective_version,
                    session_id=session_id,
                )
                _write_sse_event(self, "message", response)
                _write_sse_event(self, "done", {"status": "done"})
                self.close_connection = True
                return

            _json_response(
                self,
                200,
                response,
                allowed_origins=allowed_origins,
                protocol_version=effective_version,
                session_id=session_id,
            )

        def do_DELETE(self) -> None:  # noqa: N802
            if not self._origin_allowed():
                self._reject_disallowed_origin()
                return

            if self.path != "/mcp":
                _json_response(
                    self,
                    404,
                    {"error": "not_found"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            user_id = self._require_auth()
            if user_id is None:
                _drain_request_body(self)
                return

            try:
                session_id, session = self._resolve_session(user_id)
            except KeyError:
                self._protocol_error("session_not_found", status_code=404)
                return
            except PermissionError:
                self._protocol_error("session_owner_mismatch", status_code=403)
                return

            if session_id is None or session is None:
                self._protocol_error("missing_session")
                return

            effective_version = self._validate_protocol_version(
                session_id=session_id,
                method=None,
            )
            if effective_version is None:
                return

            removed_session = self._remove_session(session_id)
            if removed_session is not None:
                removed_session.close()

            _json_response(
                self,
                200,
                {"ok": True, "session_closed": True},
                allowed_origins=allowed_origins,
                protocol_version=effective_version,
            )

    return MCPStreamableHTTPHandler


def run_server(
    port: int,
    host: str = "127.0.0.1",
    registry: ToolRegistry | None = None,
    *,
    auth_verifier: BearerTokenVerifier | None = None,
) -> None:
    active_registry = registry or ToolRegistry.global_instance()
    handler_cls = _build_handler(
        active_registry,
        host=host,
        port=port,
        auth_verifier=auth_verifier,
    )
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[ToolAnything] MCP Streamable HTTP 已啟動：http://{host}:{port}/mcp")
    print("健康檢查：/health，工具列表：/tools")
    print("GET /mcp：建立或恢復 server->client stream（需帶 Mcp-Session-Id）")
    print("POST /mcp：JSON-RPC request/notification")
    print("DELETE /mcp：關閉 session")
    print("Legacy SSE transport 仍保留於既有 mcp_tool_server。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[ToolAnything] MCP Streamable HTTP 已停止")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="啟動 MCP Streamable HTTP transport")
    parser.add_argument("--port", type=int, default=9092, help="監聽 port，預設 9092")
    parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_server(port=args.port, host=args.host)


__all__ = ["_build_handler", "run_server", "main", "MCP_PROTOCOL_VERSION_HEADER", "MCP_SESSION_ID_HEADER"]
