"""輕量 MCP Tool Server，提供基本工具列舉與呼叫介面。"""
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
from urllib.parse import parse_qs, urlparse

from ..core.registry import ToolRegistry
from ..core.result_serializer import ResultSerializer
from ..core.security_manager import SecurityManager
from ..exceptions import ToolError
from ..protocol.mcp_jsonrpc import (
    MCPProtocolCoreImpl,
    MCPRequestContext,
    build_transport_ready_message,
)
from .mcp_streamable_http import _build_handler as _build_streamable_handler
from .mcp_runtime import build_protocol_dependencies
from ..utils.logger import configure_logging, logger

_CLIENT_DISCONNECT_ERRORS = (
    BrokenPipeError,
    ConnectionAbortedError,
    ConnectionResetError,
)


def _legacy_sse_endpoints() -> Dict[str, str]:
    return {
        "health": "/health",
        "tools": "/tools",
        "sse": "/sse",
        "messages": "/messages/{session_id}",
        "invoke": "/invoke",
        "invoke_stream": "/invoke/stream",
    }


def _legacy_sse_status_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "transport": "legacy_sse",
        "mcp": {
            "transport": "sse",
            "sse": "/sse",
            "messages": "/messages/{session_id}",
        },
        "endpoints": _legacy_sse_endpoints(),
    }


def _legacy_sse_not_found_payload(path: str) -> Dict[str, Any]:
    return {
        "error": "not_found",
        "transport": "legacy_sse",
        "path": path,
        "hint": "Legacy MCP SSE uses GET /sse then POST /messages/{session_id}.",
        "mcp": {
            "transport": "sse",
            "sse": "/sse",
            "messages": "/messages/{session_id}",
        },
    }


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


def _send_cors_headers(
    handler: BaseHTTPRequestHandler,
    *,
    allowed_origins: set[str],
) -> None:
    origin = handler.headers.get("Origin")
    if origin and ("*" in allowed_origins or origin in allowed_origins):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Max-Age", "600")


def _json_response(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    payload: Dict[str, Any],
    *,
    allowed_origins: set[str],
) -> None:
    """將 payload 序列化成 JSON 並寫入 HTTP 回應。"""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    _send_cors_headers(handler, allowed_origins=allowed_origins)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any] | None:
    """從 HTTP 請求讀取並解析 JSON body，無法解析時回傳 ``None``。"""

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
        content_length = 0
    if content_length > 0:
        handler.rfile.read(content_length)


def _send_sse_headers(
    handler: BaseHTTPRequestHandler,
    *,
    allowed_origins: set[str],
    status_code: int = 200,
) -> None:
    """送出 SSE 回應標頭。"""

    handler.send_response(status_code)
    _send_cors_headers(handler, allowed_origins=allowed_origins)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()


def _write_sse_event(handler: BaseHTTPRequestHandler, event: str, data: Dict[str, Any]) -> None:
    """寫入單筆 SSE event。"""

    payload = json.dumps(data, ensure_ascii=False)
    handler.wfile.write(f"event: {event}\n".encode("utf-8"))
    for line in payload.splitlines():
        handler.wfile.write(f"data: {line}\n".encode("utf-8"))
    handler.wfile.write(b"\n")
    handler.wfile.flush()


@dataclass(slots=True)
class SSESession:
    handler: BaseHTTPRequestHandler
    user_id: str = "default"
    lock: threading.Lock = field(default_factory=threading.Lock)
    active: bool = True


_SSE_SESSIONS: dict[str, SSESession] = {}
_SSE_SESSIONS_LOCK = threading.Lock()


def _register_sse_session(session_id: str, session: SSESession) -> None:
    with _SSE_SESSIONS_LOCK:
        _SSE_SESSIONS[session_id] = session


def _get_sse_session(session_id: str) -> SSESession | None:
    with _SSE_SESSIONS_LOCK:
        return _SSE_SESSIONS.get(session_id)


def _remove_sse_session(session_id: str) -> None:
    with _SSE_SESSIONS_LOCK:
        _SSE_SESSIONS.pop(session_id, None)


def _write_sse_event_locked(session: SSESession, event: str, data: Dict[str, Any]) -> bool:
    payload = json.dumps(data, ensure_ascii=False)
    message = f"event: {event}\n"
    for line in payload.splitlines():
        message += f"data: {line}\n"
    message += "\n"

    try:
        with session.lock:
            session.handler.wfile.write(message.encode("utf-8"))
            session.handler.wfile.flush()
        return True
    except _CLIENT_DISCONNECT_ERRORS:
        logger.warning("MCP SSE client disconnected")
        return False
    except Exception:
        logger.exception("MCP SSE 寫入失敗")
        return False

def _build_legacy_handler(
    registry: ToolRegistry,
    *,
    host: str,
    port: int,
    serializer: ResultSerializer | None = None,
    security_manager: SecurityManager | None = None,
) -> type[BaseHTTPRequestHandler]:
    """建立綁定指定 registry 的 ``BaseHTTPRequestHandler`` 子類別。"""

    active_serializer = serializer or ResultSerializer()
    active_security_manager = security_manager or SecurityManager()
    allowed_origins = _build_allowed_origins(host, port)
    protocol_core = MCPProtocolCoreImpl()
    mcp_adapter, active_serializer, active_security_manager, protocol_deps = build_protocol_dependencies(
        registry,
        serializer=active_serializer,
        security_manager=active_security_manager,
    )

    class MCPToolHandler(BaseHTTPRequestHandler):
        server_version = "ToolAnythingMCP/0.1"
        protocol_version = "HTTP/1.1"

        def handle(self) -> None:  # noqa: D401 - stdlib hook
            """處理單一 HTTP 連線，忽略 client 主動中止造成的例外。"""

            try:
                super().handle()
            except _CLIENT_DISCONNECT_ERRORS:
                logger.warning("MCP HTTP client disconnected")

        def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - 使用預設 logging 行為
            super().log_message(format, *args)

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
            )

        def do_OPTIONS(self) -> None:  # noqa: N802 - 標準庫接口
            parsed = urlparse(self.path)
            if not self._origin_allowed():
                self._reject_disallowed_origin()
                return
            if (
                parsed.path in {"/", "/health", "/tools", "/sse", "/invoke", "/invoke/stream"}
                or parsed.path.startswith("/messages/")
            ):
                self.send_response(204)
                _send_cors_headers(self, allowed_origins=allowed_origins)
                self.end_headers()
                return

            _json_response(
                self,
                404,
                _legacy_sse_not_found_payload(parsed.path),
                allowed_origins=allowed_origins,
            )

        def do_GET(self) -> None:  # noqa: N802 - 標準庫接口
            parsed = urlparse(self.path)
            if not self._origin_allowed():
                self._reject_disallowed_origin()
                return
            if parsed.path == "/sse":
                session_id = uuid.uuid4().hex
                user_id = parse_qs(parsed.query).get("user_id", ["default"])[0] or "default"
                session = SSESession(self, user_id=user_id)
                _register_sse_session(session_id, session)
                _send_sse_headers(self, allowed_origins=allowed_origins, status_code=200)
                _write_sse_event(
                    self,
                    "message",
                    build_transport_ready_message(session_id),
                )

                last_ping = time.monotonic()
                try:
                    while session.active:
                        time.sleep(1)
                        if time.monotonic() - last_ping >= 15:
                            alive = _write_sse_event_locked(session, "ping", {"ts": time.time()})
                            if not alive:
                                session.active = False
                                break
                            last_ping = time.monotonic()
                except Exception:
                    logger.exception("MCP SSE 連線中斷")
                finally:
                    session.active = False
                    _remove_sse_session(session_id)
                return

            if parsed.path == "/" or parsed.path == "/health":
                _json_response(
                    self,
                    200,
                    _legacy_sse_status_payload(),
                    allowed_origins=allowed_origins,
                )
                return

            if parsed.path == "/tools":
                _json_response(
                    self,
                    200,
                    {"tools": registry.to_mcp_tools()},
                    allowed_origins=allowed_origins,
                )
                return

            _json_response(
                self,
                404,
                _legacy_sse_not_found_payload(parsed.path),
                allowed_origins=allowed_origins,
            )

        def _handle_invoke(self) -> tuple[int, Dict[str, Any]]:
            payload = _read_json(self)
            if payload is None:
                return 400, {"error": "invalid_json"}

            name: str | None = payload.get("name")
            arguments: Dict[str, Any] = payload.get("arguments", {}) or {}
            user_id: str | None = payload.get("user_id")
            audit_log = active_security_manager.audit_call(name or "", arguments, user_id)

            if not isinstance(name, str):
                return 400, {"error": "missing_name"}

            try:
                result = registry.execute_tool(
                    name,
                    arguments=arguments,
                    user_id=user_id,
                    state_manager=None,
                )
                serialized = active_serializer.to_mcp(result)
                return (
                    200,
                    {
                        "name": name,
                        "arguments": active_security_manager.mask_keys_in_log(arguments),
                        "result": serialized,
                        "raw_result": result,
                        "audit": audit_log,
                    },
                )
            except ToolError as exc:  # pragma: no cover - runtime error handling
                return (
                    400,
                    {
                        "error": exc.to_dict(),
                        "arguments": active_security_manager.mask_keys_in_log(arguments),
                        "audit": audit_log,
                    },
                )
            except Exception:  # pragma: no cover - runtime error handling
                logger.exception("工具執行時發生未預期錯誤: %s", name)
                return (
                    500,
                    {
                        "error": {"type": "internal_error", "message": "工具執行時發生未預期錯誤"},
                        "arguments": active_security_manager.mask_keys_in_log(arguments),
                        "audit": audit_log,
                    },
                )

        def _handle_invoke_stream(self) -> None:
            _send_sse_headers(self, allowed_origins=allowed_origins, status_code=200)
            try:
                status_code, payload = self._handle_invoke()
                if status_code == 200:
                    _write_sse_event(self, "result", payload)
                else:
                    _write_sse_event(
                        self,
                        "error",
                        {
                            "status_code": status_code,
                            "payload": payload,
                        },
                    )
            except Exception:  # pragma: no cover - runtime error handling
                logger.exception("SSE 工具呼叫時發生未預期錯誤")
                _write_sse_event(
                    self,
                    "error",
                    {
                        "status_code": 500,
                        "payload": {
                            "error": {
                                "type": "internal_error",
                                "message": "SSE 工具呼叫時發生未預期錯誤",
                            }
                        },
                    },
                )
            _write_sse_event(self, "done", {"status": "done"})

        def do_POST(self) -> None:  # noqa: N802 - 標準庫接口
            parsed = urlparse(self.path)
            if not self._origin_allowed():
                _drain_request_body(self)
                self._reject_disallowed_origin()
                return
            if parsed.path == "/invoke":
                status_code, payload = self._handle_invoke()
                _json_response(self, status_code, payload, allowed_origins=allowed_origins)
                return

            if parsed.path == "/invoke/stream":
                self._handle_invoke_stream()
                return

            if parsed.path.startswith("/messages"):
                session_id = None
                if parsed.path == "/messages":
                    session_id = parse_qs(parsed.query).get("session_id", [None])[0]
                elif parsed.path.startswith("/messages/"):
                    session_id = parsed.path.split("/", 2)[2]

                if not session_id:
                    _drain_request_body(self)
                    _json_response(
                        self,
                        400,
                        {"error": "missing_session"},
                        allowed_origins=allowed_origins,
                    )
                    return

                session = _get_sse_session(session_id)
                if session is None or not session.active:
                    _drain_request_body(self)
                    _json_response(
                        self,
                        404,
                        {"error": "session_not_found"},
                        allowed_origins=allowed_origins,
                    )
                    return

                payload = _read_json(self)
                if payload is None:
                    _json_response(
                        self,
                        400,
                        {"error": "invalid_json"},
                        allowed_origins=allowed_origins,
                    )
                    return

                context = MCPRequestContext(
                    user_id=session.user_id,
                    session_id=session_id,
                    transport="sse",
                )
                response = protocol_core.handle(
                    payload,
                    context=context,
                    deps=protocol_deps,
                )
                if response is not None:
                    sent = _write_sse_event_locked(session, "message", response)
                    if not sent:
                        session.active = False
                        _remove_sse_session(session_id)

                _json_response(
                    self,
                    200,
                    {"status": "accepted"},
                    allowed_origins=allowed_origins,
                )
                return

            _drain_request_body(self)
            _json_response(
                self,
                404,
                _legacy_sse_not_found_payload(parsed.path),
                allowed_origins=allowed_origins,
            )

    return MCPToolHandler


def _build_handler(
    registry: ToolRegistry,
    *,
    host: str,
    port: int,
    serializer: ResultSerializer | None = None,
    security_manager: SecurityManager | None = None,
) -> type[BaseHTTPRequestHandler]:
    """建立同時支援 Streamable HTTP 與 legacy SSE 的 HTTP handler。"""

    legacy_handler_cls = _build_legacy_handler(
        registry,
        host=host,
        port=port,
        serializer=serializer,
        security_manager=security_manager,
    )
    streamable_handler_cls = _build_streamable_handler(
        registry,
        host=host,
        port=port,
        serializer=serializer,
        security_manager=security_manager,
    )

    class MCPToolHandler(streamable_handler_cls, legacy_handler_cls):
        server_version = "ToolAnythingMCP/0.2"
        protocol_version = "HTTP/1.1"

        def handle(self) -> None:  # noqa: D401 - stdlib hook
            """處理單一 HTTP 連線，忽略 client 主動中止造成的例外。"""

            try:
                super().handle()
            except _CLIENT_DISCONNECT_ERRORS:
                logger.warning("MCP HTTP client disconnected")

        def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            if parsed.path == "/mcp":
                return streamable_handler_cls.do_OPTIONS(self)
            return legacy_handler_cls.do_OPTIONS(self)

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            if parsed.path == "/mcp":
                return streamable_handler_cls.do_GET(self)
            return legacy_handler_cls.do_GET(self)

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/mcp"}:
                original_path = self.path
                try:
                    if parsed.path == "/":
                        self.path = "/mcp"
                    return streamable_handler_cls.do_POST(self)
                finally:
                    self.path = original_path
            return legacy_handler_cls.do_POST(self)

        def do_DELETE(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            if parsed.path == "/mcp":
                return streamable_handler_cls.do_DELETE(self)
            return streamable_handler_cls.do_DELETE(self)

    return MCPToolHandler


def run_server(port: int, host: str = "127.0.0.1", registry: ToolRegistry | None = None) -> None:
    """啟動 HTTP 形式的 MCP Tool Server。"""

    active_registry = registry or ToolRegistry.global_instance()
    handler_cls = _build_handler(active_registry, host=host, port=port)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[ToolAnything] MCP Tool Server 已啟動：http://{host}:{port}")
    print("健康檢查：/health，工具列表：/tools")
    print("新版 MCP：POST /mcp（或容錯接受 POST /），GET /mcp，DELETE /mcp")
    print("Legacy MCP SSE：GET /sse（回傳 endpoint 供 POST /messages/{session_id} 使用）")
    print("工具呼叫：POST /invoke，SSE 呼叫工具：POST /invoke/stream（text/event-stream）")
    print("預設僅允許 localhost Origin；可用 TOOLANYTHING_ALLOWED_ORIGINS 覆寫。")

    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - CLI 停止
        print("[ToolAnything] MCP Tool Server 已停止")


def _parse_args() -> argparse.Namespace:
    """解析 CLI 參數，取得 host 與 port 設定。"""

    parser = argparse.ArgumentParser(description="啟動內建 MCP Tool Server")
    parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    return parser.parse_args()


def main() -> None:
    """CLI 入口，解析參數並啟動伺服器。"""

    configure_logging()
    try:
        args = _parse_args()
        run_server(port=args.port, host=args.host)
    except Exception:  # pragma: no cover - runtime error handling
        logger.exception("MCP Tool Server 啟動失敗")
        print("[ToolAnything] MCP Tool Server 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
