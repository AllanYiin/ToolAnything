"""輕量 MCP Tool Server，提供基本工具列舉與呼叫介面。"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import urlparse

from toolanything.core.registry import ToolRegistry


def _json_response(handler: BaseHTTPRequestHandler, status_code: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
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


def _build_handler(registry: ToolRegistry) -> type[BaseHTTPRequestHandler]:
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

        def do_POST(self) -> None:  # noqa: N802 - 標準庫接口
            parsed = urlparse(self.path)
            if parsed.path != "/invoke":
                _json_response(self, 404, {"error": "not_found"})
                return

            payload = _read_json(self)
            if payload is None:
                _json_response(self, 400, {"error": "invalid_json"})
                return

            name = payload.get("name")
            arguments = payload.get("arguments", {}) or {}
            user_id = payload.get("user_id")

            if not isinstance(name, str):
                _json_response(self, 400, {"error": "missing_name"})
                return

            try:
                result = registry.execute_tool(
                    name,
                    arguments=arguments,
                    user_id=user_id,
                    state_manager=None,
                )
            except Exception as exc:  # pragma: no cover - runtime error handling
                _json_response(self, 500, {"error": str(exc)})
                return

            _json_response(self, 200, {"name": name, "result": result})

    return MCPToolHandler


def run_server(port: int, host: str = "0.0.0.0", registry: ToolRegistry | None = None) -> None:
    """啟動 HTTP 形式的 MCP Tool Server。"""

    active_registry = registry or ToolRegistry.global_instance()
    handler_cls = _build_handler(active_registry)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[ToolAnything] MCP Tool Server 已啟動：http://{host}:{port}")
    print("健康檢查：/health，工具列表：/tools，呼叫工具：POST /invoke")

    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - CLI 停止
        print("[ToolAnything] MCP Tool Server 已停止")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="啟動內建 MCP Tool Server")
    parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_server(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
