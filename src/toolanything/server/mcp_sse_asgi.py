"""ASGI 版本的 MCP SSE Server，提供 ChatGPT App 可用的 SSE 傳輸層。"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from threading import Lock
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.core.registry import ToolRegistry
from toolanything.core.result_serializer import ResultSerializer
from toolanything.core.security_manager import SecurityManager
from toolanything.exceptions import ToolError
from toolanything.utils.logger import configure_logging, logger

app = FastAPI(title="ToolAnything MCP SSE (ASGI)")

registry: ToolRegistry | None = None
adapter: MCPAdapter | None = None
serializer: ResultSerializer | None = None
security_manager: SecurityManager | None = None

_sessions: Dict[str, asyncio.Queue] = {}
_sessions_lock: asyncio.Lock | None = None

_sessions_lock_guard = Lock()



def _get_sessions_lock() -> asyncio.Lock:
    global _sessions_lock
    if _sessions_lock is None:

        with _sessions_lock_guard:
            if _sessions_lock is None:
                _sessions_lock = asyncio.Lock()

    return _sessions_lock


def _sse(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n"


@app.on_event("startup")
async def startup() -> None:
    global registry, adapter, serializer, security_manager
    configure_logging()
    try:
        registry = ToolRegistry.global_instance()
        adapter = MCPAdapter(registry)
        serializer = ResultSerializer()
        security_manager = SecurityManager()
    except Exception:
        logger.exception("ASGI MCP SSE Server 初始化失敗")
        raise


async def _register_session(session_id: str, queue: asyncio.Queue) -> None:
    async with _get_sessions_lock():
        _sessions[session_id] = queue


async def _get_session(session_id: str) -> asyncio.Queue | None:
    async with _get_sessions_lock():
        return _sessions.get(session_id)


async def _remove_session(session_id: str) -> None:
    async with _get_sessions_lock():
        _sessions.pop(session_id, None)


def _build_mcp_response(
    request_payload: Dict[str, Any],
    registry: ToolRegistry,
    adapter: MCPAdapter,
    serializer: ResultSerializer,
    security_manager: SecurityManager,
) -> Dict[str, Any] | None:
    method = request_payload.get("method")
    request_id = request_payload.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": adapter.to_capabilities(),
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
        params = request_payload.get("params", {}) or {}
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
            logger.exception("MCP tools/call 發生未預期錯誤")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "internal_error",
                    "data": {
                        "arguments": masked_args,
                        "audit": audit_log,
                    },
                },
            }

    if request_id is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "method_not_found"},
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/sse")
async def sse(_: Request) -> StreamingResponse:
    session_id = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    await _register_session(session_id, queue)

    async def event_stream():
        yield _sse(
            {
                "jsonrpc": "2.0",
                "method": "transport/ready",
                "params": {
                    "transport": {
                        "type": "sse",
                        "messageEndpoint": f"/messages/{session_id}",
                    }
                },
            }
        )

        try:
            while True:
                message = await queue.get()
                yield _sse(message)
        except asyncio.CancelledError:
            logger.info("MCP SSE 客戶端已中斷連線")
        finally:
            await _remove_session(session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/messages/{session_id}")
async def handle_message(session_id: str, request: Request) -> JSONResponse | Dict[str, Any]:
    if registry is None or adapter is None or serializer is None or security_manager is None:
        return JSONResponse({"error": "server_not_ready"}, status_code=503)

    queue = await _get_session(session_id)
    if queue is None:
        return JSONResponse({"error": "session_not_found"}, status_code=404)

    try:
        payload = await request.json()
    except Exception:
        logger.exception("MCP SSE 解析 JSON 失敗")
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    response = _build_mcp_response(payload, registry, adapter, serializer, security_manager)
    if response is not None:
        await queue.put(response)

    return {"ok": True}


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """透過 uvicorn 啟動 ASGI MCP SSE Server。"""

    import uvicorn

    uvicorn.run("toolanything.server.mcp_sse_asgi:app", host=host, port=port)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="啟動 ASGI MCP SSE Server")
    parser.add_argument("--port", type=int, default=8080, help="監聽 port，預設 8080")
    parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    try:
        args = _parse_args()
        run_server(host=args.host, port=args.port)
    except Exception:  # pragma: no cover - runtime error handling
        logger.exception("ASGI MCP SSE Server 啟動失敗")
        print("[ToolAnything] ASGI MCP SSE Server 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
