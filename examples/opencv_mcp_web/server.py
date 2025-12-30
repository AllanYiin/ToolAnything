"""OpenCV MCP Server + Web Client Demo."""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import logging
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from toolanything import ToolRegistry, tool
from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.core.result_serializer import ResultSerializer
from toolanything.core.security_manager import SecurityManager
from toolanything.exceptions import ToolError

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8")],
)

registry = ToolRegistry()
mcp_adapter = MCPAdapter(registry)
_SSE_SESSIONS: dict[str, "SSESession"] = {}
_SSE_SESSIONS_LOCK = threading.Lock()


class HostRuntimeConfig:
    def __init__(
        self,
        *,
        name: str | None = None,
        allow_inbound_sse: bool = True,
        sse_block_reason: str | None = None,
        sse_block_warning: str | None = None,
    ) -> None:
        self.name = name
        self.allow_inbound_sse = allow_inbound_sse
        self.sse_block_reason = sse_block_reason
        self.sse_block_warning = sse_block_warning


def _resolve_host_runtime() -> HostRuntimeConfig:
    return HostRuntimeConfig()


class SSESession:
    def __init__(self, handler: BaseHTTPRequestHandler) -> None:
        self.handler = handler
        self.lock = threading.Lock()
        self.active = True


def _decode_image(image_base64: str) -> np.ndarray:
    if not image_base64:
        raise ToolError("未收到圖片內容", error_type="missing_image")

    if image_base64.startswith("data:"):
        _, _, payload = image_base64.partition(",")
        image_base64 = payload

    try:
        binary = base64.b64decode(image_base64, validate=True)
    except (ValueError, binascii.Error) as exc:  # type: ignore[name-defined]
        raise ToolError("圖片內容無法解碼", error_type="invalid_base64") from exc

    try:
        array = np.frombuffer(binary, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
    except Exception as exc:
        raise ToolError("圖片解析失敗", error_type="decode_failed") from exc

    if image is None:
        raise ToolError("圖片格式不支援或內容損壞", error_type="decode_failed")

    return image


def _encode_image(image: np.ndarray) -> str:
    try:
        success, buffer = cv2.imencode(".png", image)
    except Exception as exc:
        raise ToolError("圖片轉碼失敗", error_type="encode_failed") from exc

    if not success:
        raise ToolError("圖片轉碼失敗", error_type="encode_failed")

    encoded = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _image_metadata(image: np.ndarray) -> dict[str, Any]:
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else image.shape[2]
    return {"width": width, "height": height, "channels": channels}


@tool(name="opencv.info", description="取得圖片尺寸與通道數", registry=registry)
def opencv_info(image_base64: str) -> dict[str, Any]:
    image = _decode_image(image_base64)
    return _image_metadata(image)


@tool(name="opencv.resize", description="依照指定尺寸縮放圖片（保持比例）", registry=registry)
def opencv_resize(
    image_base64: str,
    target_width: int | None = None,
    target_height: int | None = None,
) -> dict[str, Any]:
    image = _decode_image(image_base64)
    original_height, original_width = image.shape[:2]

    if target_width is None and target_height is None:
        raise ToolError("請至少提供寬度或高度", error_type="missing_dimension")

    if target_width is not None and target_width <= 0:
        raise ToolError("寬度必須大於 0", error_type="invalid_dimension")

    if target_height is not None and target_height <= 0:
        raise ToolError("高度必須大於 0", error_type="invalid_dimension")

    if target_width is None:
        scale = target_height / original_height
    elif target_height is None:
        scale = target_width / original_width
    else:
        scale = min(target_width / original_width, target_height / original_height)
    new_width = max(1, int(original_width * scale))
    new_height = max(1, int(original_height * scale))

    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return {
        "image_base64": _encode_image(resized),
        "width": new_width,
        "height": new_height,
    }


@tool(name="opencv.canny", description="Canny 邊緣偵測", registry=registry)
def opencv_canny(
    image_base64: str,
    threshold1: int = 50,
    threshold2: int = 150,
) -> dict[str, Any]:
    if threshold1 < 0 or threshold2 < 0:
        raise ToolError("閾值必須為非負整數", error_type="invalid_threshold")

    image = _decode_image(image_base64)
    try:
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        edges = cv2.Canny(gray, threshold1, threshold2)
    except Exception as exc:
        raise ToolError("邊緣偵測失敗", error_type="canny_failed") from exc

    return {
        "image_base64": _encode_image(edges),
        **_image_metadata(edges),
    }


def _json_response(handler: BaseHTTPRequestHandler, status_code: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
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


def _send_sse_event(handler: BaseHTTPRequestHandler, event: str, payload: Dict[str, Any]) -> None:
    message = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    try:
        handler.wfile.write(message.encode("utf-8"))
        handler.wfile.flush()
    except BrokenPipeError:
        logging.warning("SSE client disconnected")


def _send_sse_event_locked(session: SSESession, event: str, payload: Dict[str, Any]) -> bool:
    message = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    try:
        with session.lock:
            session.handler.wfile.write(message.encode("utf-8"))
            session.handler.wfile.flush()
        return True
    except BrokenPipeError:
        logging.warning("MCP SSE client disconnected")
        return False
    except Exception as exc:
        logging.error("MCP SSE 寫入失敗: %s", exc, exc_info=True)
        return False


def _send_sse_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()


def _register_sse_session(session_id: str, session: SSESession) -> None:
    with _SSE_SESSIONS_LOCK:
        _SSE_SESSIONS[session_id] = session


def _get_sse_session(session_id: str) -> SSESession | None:
    with _SSE_SESSIONS_LOCK:
        return _SSE_SESSIONS.get(session_id)


def _remove_sse_session(session_id: str) -> None:
    with _SSE_SESSIONS_LOCK:
        _SSE_SESSIONS.pop(session_id, None)


def _build_mcp_response(
    request: Dict[str, Any],
    *,
    registry: ToolRegistry,
    serializer: ResultSerializer,
    security_manager: SecurityManager,
) -> Dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": mcp_adapter.to_capabilities(),
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": registry.to_mcp_tools()},
        }

    if method == "tools/call":
        params = request.get("params", {}) or {}
        name = params.get("name")
        arguments: Dict[str, Any] = params.get("arguments", {}) or {}
        masked_args = security_manager.mask_keys_in_log(arguments)
        audit_log = security_manager.audit_call(name or "", arguments, "default")

        try:
            result = registry.execute_tool(
                name,
                arguments=arguments,
                user_id="default",
                state_manager=None,
            )
            serialized = serializer.to_mcp(result)
            text_content = (
                json.dumps(serialized["content"], ensure_ascii=False)
                if serialized.get("contentType") == "application/json"
                else str(serialized.get("content"))
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": text_content}],
                    "meta": {"contentType": serialized.get("contentType")},
                    "arguments": masked_args,
                    "audit": audit_log,
                },
                "raw_result": result,
            }
        except ToolError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32001,
                    "message": exc.error_type,
                    "data": {
                        "message": str(exc),
                        "details": exc.data,
                        "arguments": masked_args,
                        "audit": audit_log,
                    },
                },
            }
        except Exception:
            logging.error("MCP tools/call 發生未預期錯誤", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "internal_error",
                    "data": {"arguments": masked_args, "audit": audit_log},
                },
            }

    if request_id is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "method_not_found"},
    }



def _read_static(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _discard_request_body(handler: BaseHTTPRequestHandler) -> None:
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        content_length = 0

    if content_length > 0:
        handler.rfile.read(content_length)


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".js":
        return "application/javascript; charset=utf-8"
    if suffix in {".png", ".jpg", ".jpeg", ".gif"}:
        return f"image/{suffix.lstrip('.')}"
    return "text/html; charset=utf-8"


def _build_handler(
    registry: ToolRegistry,
    *,
    serializer: ResultSerializer | None = None,
    security_manager: SecurityManager | None = None,
    host_runtime: HostRuntimeConfig | None = None,
) -> type[BaseHTTPRequestHandler]:
    active_serializer = serializer or ResultSerializer()
    active_security_manager = security_manager or SecurityManager()
    active_host_runtime = host_runtime or HostRuntimeConfig()

    class MCPWebHandler(BaseHTTPRequestHandler):
        server_version = "ToolAnythingMCPWeb/0.1"
        protocol_version = "HTTP/1.1"

        def _set_cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def log_message(self, format: str, *args: Any) -> None:
            super().log_message(format, *args)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._set_cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/sse":
                _discard_request_body(self)
                if not active_host_runtime.allow_inbound_sse:
                    _json_response(
                        self,
                        503,
                        {
                            "error": "sse_not_supported",
                            "reason": active_host_runtime.sse_block_reason,
                            "warning": active_host_runtime.sse_block_warning,
                        },
                    )
                    return
                session_id = uuid.uuid4().hex
                session = SSESession(self)
                _register_sse_session(session_id, session)
                _send_sse_headers(self)
                _send_sse_event(self, "endpoint", {"uri": f"/messages/{session_id}"})

                last_ping = time.monotonic()
                try:
                    while session.active:
                        time.sleep(1)
                        if time.monotonic() - last_ping >= 15:
                            alive = _send_sse_event_locked(session, "ping", {"ts": time.time()})
                            if not alive:
                                session.active = False
                                break
                            last_ping = time.monotonic()
                except Exception as exc:
                    logging.error("MCP SSE 連線中斷: %s", exc, exc_info=True)
                finally:
                    session.active = False
                    _remove_sse_session(session_id)
                return

            if parsed.path in {"/", "/index.html"}:
                _discard_request_body(self)
                file_path = WEB_DIR / "index.html"
                return self._serve_static(file_path)

            if parsed.path == "/health":
                _discard_request_body(self)
                _json_response(self, 200, {"status": "ok"})
                return

            if parsed.path == "/tools":
                _discard_request_body(self)
                _json_response(self, 200, {"tools": registry.to_mcp_tools()})
                return

            candidate = (WEB_DIR / parsed.path.lstrip("/")).resolve()
            if WEB_DIR in candidate.parents and candidate.is_file():
                _discard_request_body(self)
                return self._serve_static(candidate)

            _discard_request_body(self)
            _json_response(self, 404, {"error": "not_found"})

        def _serve_static(self, file_path: Path) -> None:
            content = _read_static(file_path)
            if content is None:
                _json_response(self, 404, {"error": "not_found"})
                return

            content_type = _guess_content_type(file_path)
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self._set_cors()
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/sse":
                if not active_host_runtime.allow_inbound_sse:
                    _json_response(
                        self,
                        503,
                        {
                            "error": "sse_not_supported",
                            "reason": active_host_runtime.sse_block_reason,
                            "warning": active_host_runtime.sse_block_warning,
                        },
                    )
                    return
                _json_response(self, 405, {"error": "method_not_allowed"})
                return
            if parsed.path.startswith("/messages"):
                session_id = None
                if parsed.path == "/messages":
                    session_id = parse_qs(parsed.query).get("session_id", [None])[0]
                elif parsed.path.startswith("/messages/"):
                    session_id = parsed.path.split("/", 2)[2]

                if not session_id:
                    _json_response(self, 400, {"error": "missing_session"})
                    return

                session = _get_sse_session(session_id)
                if session is None or not session.active:
                    _json_response(self, 404, {"error": "session_not_found"})
                    return

                payload = _read_json(self)
                if payload is None:
                    _json_response(self, 400, {"error": "invalid_json"})
                    return

                response = _build_mcp_response(
                    payload,
                    registry=registry,
                    serializer=active_serializer,
                    security_manager=active_security_manager,
                )
                if response is not None:
                    sent = _send_sse_event_locked(session, "message", response)
                    if not sent:
                        session.active = False
                        _remove_sse_session(session_id)

                _json_response(self, 200, {"status": "accepted"})
                return

            if parsed.path == "/invoke-sse":
                if not active_host_runtime.allow_inbound_sse:
                    _json_response(
                        self,
                        503,
                        {
                            "error": "sse_not_supported",
                            "reason": active_host_runtime.sse_block_reason,
                            "warning": active_host_runtime.sse_block_warning,
                        },
                    )
                    return
                payload = _read_json(self)
                if payload is None:
                    _json_response(self, 400, {"error": "invalid_json"})
                    return

                name: str | None = payload.get("name")
                arguments: Dict[str, Any] = payload.get("arguments", {}) or {}
                user_id: str | None = payload.get("user_id")
                audit_log = active_security_manager.audit_call(name or "", arguments, user_id)

                if not isinstance(name, str):
                    _json_response(self, 400, {"error": "missing_name"})
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")

                self.send_header("X-Accel-Buffering", "no")

                self._set_cors()
                self.end_headers()

                try:
                    _send_sse_event(self, "progress", {"progress": 10, "message": "開始處理"})
                    result = registry.execute_tool(
                        name,
                        arguments=arguments,
                        user_id=user_id,
                        state_manager=None,
                    )
                    _send_sse_event(self, "progress", {"progress": 70, "message": "完成工具運算"})
                    serialized = active_serializer.to_mcp(result)
                    _send_sse_event(
                        self,
                        "result",
                        {
                            "name": name,
                            "arguments": active_security_manager.mask_keys_in_log(arguments),
                            "result": serialized,
                            "raw_result": result,
                            "audit": audit_log,
                        },
                    )
                    _send_sse_event(self, "progress", {"progress": 100, "message": "輸出完成"})
                    _send_sse_event(self, "done", {"status": "ok"})
                except ToolError as exc:
                    logging.warning("Tool error: %s", exc, exc_info=True)
                    _send_sse_event(
                        self,
                        "error",
                        {
                            "error": exc.to_dict(),
                            "arguments": active_security_manager.mask_keys_in_log(arguments),
                            "audit": audit_log,
                        },
                    )
                    _send_sse_event(self, "done", {"status": "error"})
                except Exception as exc:
                    logging.error("Unhandled tool error: %s", exc, exc_info=True)
                    _send_sse_event(
                        self,
                        "error",
                        {
                            "error": {"type": "internal_error", "message": "工具執行時發生未預期錯誤"},
                            "arguments": active_security_manager.mask_keys_in_log(arguments),
                            "audit": audit_log,
                        },
                    )
                    _send_sse_event(self, "done", {"status": "error"})

                self.close_connection = True

                return

            if parsed.path != "/invoke":
                _json_response(self, 404, {"error": "not_found"})
                return

            payload = _read_json(self)
            if payload is None:
                _json_response(self, 400, {"error": "invalid_json"})
                return

            name: str | None = payload.get("name")
            arguments: Dict[str, Any] = payload.get("arguments", {}) or {}
            user_id: str | None = payload.get("user_id")
            audit_log = active_security_manager.audit_call(name or "", arguments, user_id)

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
                serialized = active_serializer.to_mcp(result)
                _json_response(
                    self,
                    200,
                    {
                        "name": name,
                        "arguments": active_security_manager.mask_keys_in_log(arguments),
                        "result": serialized,
                        "raw_result": result,
                        "audit": audit_log,
                    },
                )
            except ToolError as exc:
                logging.warning("Tool error: %s", exc, exc_info=True)
                _json_response(
                    self,
                    400,
                    {
                        "error": exc.to_dict(),
                        "arguments": active_security_manager.mask_keys_in_log(arguments),
                        "audit": audit_log,
                    },
                )
            except Exception as exc:
                logging.error("Unhandled tool error: %s", exc, exc_info=True)
                _json_response(
                    self,
                    500,
                    {
                        "error": {"type": "internal_error", "message": "工具執行時發生未預期錯誤"},
                        "arguments": active_security_manager.mask_keys_in_log(arguments),
                        "audit": audit_log,
                    },
                )

    return MCPWebHandler


def start_server(port: int, host: str = "0.0.0.0") -> None:
    host_runtime = _resolve_host_runtime()
    handler_cls = _build_handler(registry, host_runtime=host_runtime)
    server = ThreadingHTTPServer((host, port), handler_cls)
    logging.info("MCP Web Server 啟動：http://%s:%s", host, port)
    print(f"[opencv_mcp_web] 伺服器已啟動：http://{host}:{port}")
    print("健康檢查：/health，工具列表：/tools，呼叫工具：POST /invoke-sse（SSE）")
    print("MCP SSE：GET /sse（回傳 endpoint 供 POST /messages/{session_id} 使用）")
    if not host_runtime.allow_inbound_sse:
        print(
            "[opencv_mcp_web] 偵測到不支援 inbound SSE 的環境，已停用 /sse 與 /invoke-sse"
        )
        if host_runtime.sse_block_reason:
            print(f"[opencv_mcp_web] 原因：{host_runtime.sse_block_reason}")
        if host_runtime.sse_block_warning:
            print(f"[opencv_mcp_web] 提醒：{host_runtime.sse_block_warning}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[opencv_mcp_web] 伺服器已停止")
    except Exception as exc:
        logging.error("Server crashed: %s", exc, exc_info=True)
        raise


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="啟動 OpenCV MCP Web Demo")
    parser.add_argument("--port", type=int, default=9091, help="監聽 port，預設 9091")
    parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    print("[opencv_mcp_web] 可用工具：")
    for tool_info in registry.to_mcp_tools():
        print(f" - {tool_info['name']}: {tool_info['description']}")

    try:
        start_server(port=args.port, host=args.host)
    except Exception as exc:
        logging.error("Fatal error: %s", exc, exc_info=True)
        print("[opencv_mcp_web] 啟動失敗，請查看 logs/server.log")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
