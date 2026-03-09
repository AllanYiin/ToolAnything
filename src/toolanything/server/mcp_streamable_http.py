"""MCP Streamable HTTP transport.

This is the recommended HTTP transport. The existing SSE transport remains as a
legacy compatibility layer.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import uuid
from dataclasses import dataclass
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
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header(
        "Access-Control-Allow-Headers",
        f"Content-Type, Authorization, {MCP_PROTOCOL_VERSION_HEADER}, {MCP_SESSION_ID_HEADER}",
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


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any] | None:
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        return None

    raw_body = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    try:
        return json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


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


def _write_sse_event(handler: BaseHTTPRequestHandler, event: str, data: Dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    handler.wfile.write(f"event: {event}\n".encode("utf-8"))
    for line in payload.splitlines():
        handler.wfile.write(f"data: {line}\n".encode("utf-8"))
    handler.wfile.write(b"\n")
    handler.wfile.flush()


@dataclass(slots=True)
class StreamableSession:
    user_id: str
    protocol_version: str


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    prefix = "Bearer "
    if header_value.startswith(prefix):
        return header_value[len(prefix) :].strip() or None
    return None


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

        def _resolve_user_id(self) -> str | None:
            if auth_verifier is None:
                return None

            token = _extract_bearer_token(self.headers.get("Authorization"))
            if token is None:
                return None
            return auth_verifier.verify(token)

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

        def _resolve_session(self, user_id: str) -> tuple[str | None, str]:
            session_id = self.headers.get(MCP_SESSION_ID_HEADER)
            if session_id:
                with sessions_lock:
                    session = sessions.get(session_id)
                if session is None:
                    raise KeyError("session_not_found")
                return session_id, session.user_id
            return None, user_id

        def _protocol_error(self, error: str, *, status_code: int = 400, session_id: str | None = None) -> None:
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
                if requested_version and requested_version != protocol_version:
                    self._protocol_error("unsupported_protocol_version")
                    return None
                if header_version and header_version != protocol_version:
                    self._protocol_error("unsupported_protocol_version")
                    return None
                return protocol_version

            if session_id is None:
                if header_version and header_version != protocol_version:
                    self._protocol_error("unsupported_protocol_version")
                    return None
                return header_version or protocol_version

            with sessions_lock:
                session = sessions.get(session_id)
            if session is None:
                self._protocol_error("session_not_found", status_code=404)
                return None

            effective_version = header_version or session.protocol_version
            if effective_version != session.protocol_version:
                self._protocol_error("protocol_version_mismatch", session_id=session_id)
                return None

            return effective_version

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
                return

            session_id = self.headers.get(MCP_SESSION_ID_HEADER)
            if not session_id:
                _json_response(
                    self,
                    400,
                    {"error": "missing_session"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            with sessions_lock:
                session = sessions.get(session_id)
            if session is None:
                _json_response(
                    self,
                    404,
                    {"error": "session_not_found"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            effective_version = self._validate_protocol_version(
                session_id=session_id,
                method=None,
            )
            if effective_version is None:
                return

            _send_sse_headers(
                self,
                allowed_origins=allowed_origins,
                protocol_version=effective_version,
                session_id=session_id,
            )
            _write_sse_event(self, "ready", {"session_id": session_id, "transport": "streamable_http"})

        def do_POST(self) -> None:  # noqa: N802
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

            try:
                session_id, session_user_id = self._resolve_session(user_id)
            except KeyError:
                _json_response(
                    self,
                    404,
                    {"error": "session_not_found"},
                    allowed_origins=allowed_origins,
                    protocol_version=protocol_version,
                )
                return

            method = payload.get("method")
            if method == "initialize" and session_id is None:
                effective_version = self._validate_protocol_version(
                    session_id=None,
                    method=method,
                    payload=payload,
                )
                if effective_version is None:
                    return
                session_id = uuid.uuid4().hex
                with sessions_lock:
                    sessions[session_id] = StreamableSession(
                        user_id=user_id,
                        protocol_version=effective_version,
                    )
                session_user_id = user_id
            else:
                effective_version = self._validate_protocol_version(
                    session_id=session_id,
                    method=method,
                    payload=payload,
                )
                if effective_version is None:
                    return

            context = MCPRequestContext(
                user_id=session_user_id,
                session_id=session_id,
                transport="streamable_http",
            )
            response = protocol_core.handle(
                payload,
                context=context,
                deps=protocol_deps,
            )

            wants_stream = "text/event-stream" in (self.headers.get("Accept") or "")
            if wants_stream:
                _send_sse_headers(
                    self,
                    allowed_origins=allowed_origins,
                    protocol_version=effective_version,
                    session_id=session_id,
                )
                if response is not None:
                    _write_sse_event(self, "message", response)
                _write_sse_event(self, "done", {"status": "done"})
                self.close_connection = True
                return

            _json_response(
                self,
                200,
                response or {"ok": True},
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
                session_id, _ = self._resolve_session(user_id)
            except KeyError:
                self._protocol_error("session_not_found", status_code=404)
                return

            if session_id is None:
                self._protocol_error("missing_session")
                return

            effective_version = self._validate_protocol_version(
                session_id=session_id,
                method=None,
            )
            if effective_version is None:
                return

            with sessions_lock:
                sessions.pop(session_id, None)

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
