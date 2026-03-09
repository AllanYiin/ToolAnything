"""ASGI 版本的 MCP SSE Server，提供 ChatGPT App 可用的 SSE 傳輸層。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..core.registry import ToolRegistry
from ..core.result_serializer import ResultSerializer
from ..core.security_manager import SecurityManager
from ..protocol.mcp_jsonrpc import (
    MCPProtocolCoreImpl,
    MCPRequestContext,
    build_transport_ready_message,
)
from .mcp_runtime import ProtocolDependencies, build_protocol_dependencies
from ..utils.logger import configure_logging, logger

registry: ToolRegistry | None = None
adapter = None
serializer: ResultSerializer | None = None
security_manager: SecurityManager | None = None
protocol_core: MCPProtocolCoreImpl | None = None
protocol_deps: ProtocolDependencies | None = None

@dataclass(slots=True)
class SSESession:
    queue: asyncio.Queue
    user_id: str = "default"


_sessions: Dict[str, SSESession] = {}
_sessions_lock: asyncio.Lock | None = None

_sessions_lock_guard = Lock()
_allowed_origins: set[str] = set()



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


def _origin_allowed(origin: str | None) -> bool:
    if not origin or "*" in _allowed_origins:
        return True
    return origin in _allowed_origins


async def _startup_state() -> None:
    global registry, adapter, serializer, security_manager, protocol_core, protocol_deps, _allowed_origins
    configure_logging()
    host = os.getenv("TOOLANYTHING_HOST", "127.0.0.1")
    port = int(os.getenv("TOOLANYTHING_PORT", "8080"))
    _allowed_origins = _build_allowed_origins(host, port)
    registry = ToolRegistry.global_instance()
    serializer = ResultSerializer()
    security_manager = SecurityManager()
    protocol_core = MCPProtocolCoreImpl()
    adapter, serializer, security_manager, protocol_deps = build_protocol_dependencies(
        registry,
        serializer=serializer,
        security_manager=security_manager,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await _startup_state()
        yield
    except Exception:
        logger.exception("ASGI MCP SSE Server 初始化失敗")
        raise


app = FastAPI(title="ToolAnything MCP SSE (ASGI)", lifespan=lifespan)


async def _register_session(session_id: str, session: SSESession) -> None:
    async with _get_sessions_lock():
        _sessions[session_id] = session


async def _get_session(session_id: str) -> SSESession | None:
    async with _get_sessions_lock():
        return _sessions.get(session_id)


async def _remove_session(session_id: str) -> None:
    async with _get_sessions_lock():
        _sessions.pop(session_id, None)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/sse")
async def sse(_: Request) -> StreamingResponse:
    origin = _.headers.get("Origin")
    if not _origin_allowed(origin):
        return JSONResponse({"error": "origin_not_allowed"}, status_code=403)

    session_id = uuid.uuid4().hex
    user_id = _.query_params.get("user_id", "default") or "default"
    session = SSESession(queue=asyncio.Queue(), user_id=user_id)
    await _register_session(session_id, session)

    async def event_stream():
        yield _sse(build_transport_ready_message(session_id))

        try:
            while True:
                message = await session.queue.get()
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
    if protocol_core is None or protocol_deps is None:
        return JSONResponse({"error": "server_not_ready"}, status_code=503)
    if not _origin_allowed(request.headers.get("Origin")):
        return JSONResponse({"error": "origin_not_allowed"}, status_code=403)

    session = await _get_session(session_id)
    if session is None:
        return JSONResponse({"error": "session_not_found"}, status_code=404)

    try:
        payload = await request.json()
    except Exception:
        logger.exception("MCP SSE 解析 JSON 失敗")
        return JSONResponse({"error": "invalid_json"}, status_code=400)

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
        await session.queue.put(response)

    return {"ok": True}


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """透過 uvicorn 啟動 ASGI MCP SSE Server。"""

    import uvicorn

    os.environ["TOOLANYTHING_HOST"] = host
    os.environ["TOOLANYTHING_PORT"] = str(port)
    uvicorn.run("toolanything.server.mcp_sse_asgi:app", host=host, port=port)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="啟動 ASGI MCP SSE Server")
    parser.add_argument("--port", type=int, default=8080, help="監聽 port，預設 8080")
    parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
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
