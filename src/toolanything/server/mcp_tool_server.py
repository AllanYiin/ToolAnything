"""輕量 MCP Tool Server，提供基本工具列舉與呼叫介面。"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import urlparse

from toolanything.core.registry import ToolRegistry
from toolanything.core.result_serializer import ResultSerializer
from toolanything.core.security_manager import SecurityManager
from toolanything.exceptions import ToolError
from toolanything.utils.logger import configure_logging, logger


def _json_response(handler: BaseHTTPRequestHandler, status_code: int, payload: Dict[str, Any]) -> None:
    """將 payload 序列化成 JSON 並寫入 HTTP 回應。"""

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
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


def _send_sse_headers(handler: BaseHTTPRequestHandler, status_code: int = 200) -> None:
    """送出 SSE 回應標頭。"""

    handler.send_response(status_code)
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


def _build_handler(
    registry: ToolRegistry,
    *,
    serializer: ResultSerializer | None = None,
    security_manager: SecurityManager | None = None,
) -> type[BaseHTTPRequestHandler]:
    """建立綁定指定 registry 的 ``BaseHTTPRequestHandler`` 子類別。"""

    active_serializer = serializer or ResultSerializer()
    active_security_manager = security_manager or SecurityManager()

    class MCPToolHandler(BaseHTTPRequestHandler):
        server_version = "ToolAnythingMCP/0.1"

        def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - 使用預設 logging 行為
            super().log_message(format, *args)

        def do_GET(self) -> None:  # noqa: N802 - 標準庫接口
            parsed = urlparse(self.path)
            if parsed.path == "/" or parsed.path == "/health":
                _json_response(self, 200, {"status": "ok"})
                return

            if parsed.path == "/tools":
                _json_response(self, 200, {"tools": registry.to_mcp_tools()})
                return

            _json_response(self, 404, {"error": "not_found"})

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
            _send_sse_headers(self, 200)
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
            if parsed.path == "/invoke":
                status_code, payload = self._handle_invoke()
                _json_response(self, status_code, payload)
                return

            if parsed.path == "/invoke/stream":
                self._handle_invoke_stream()
                return

            _json_response(self, 404, {"error": "not_found"})

    return MCPToolHandler


def run_server(port: int, host: str = "0.0.0.0", registry: ToolRegistry | None = None) -> None:
    """啟動 HTTP 形式的 MCP Tool Server。"""

    active_registry = registry or ToolRegistry.global_instance()
    handler_cls = _build_handler(active_registry)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[ToolAnything] MCP Tool Server 已啟動：http://{host}:{port}")
    print("健康檢查：/health，工具列表：/tools，呼叫工具：POST /invoke")
    print("SSE 呼叫工具：POST /invoke/stream（text/event-stream）")

    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - CLI 停止
        print("[ToolAnything] MCP Tool Server 已停止")


def _parse_args() -> argparse.Namespace:
    """解析 CLI 參數，取得 host 與 port 設定。"""

    parser = argparse.ArgumentParser(description="啟動內建 MCP Tool Server")
    parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
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
