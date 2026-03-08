"""FastAPI app for the built-in MCP inspector."""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .service import InspectorError, MCPInspectorService, maybe_open_browser

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _json_event(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _load_json(request: Request) -> Dict[str, Any]:
    try:
        return await request.json()
    except Exception as exc:
        raise InspectorError("請提供合法 JSON body", details={"exception": str(exc)}) from exc


def _error_response(exc: InspectorError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_dict()},
    )


def create_app(*, default_timeout: float = 8.0) -> FastAPI:
    service = MCPInspectorService(default_timeout=default_timeout)
    app = FastAPI(title="ToolAnything MCP Inspector", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.post("/api/connection/test")
    async def connection_test(request: Request) -> JSONResponse:
        try:
            payload = await _load_json(request)
            return JSONResponse(service.test_connection(payload.get("connection") or payload))
        except InspectorError as exc:
            return _error_response(exc)

    @app.post("/api/tools/list")
    async def tools_list(request: Request) -> JSONResponse:
        try:
            payload = await _load_json(request)
            return JSONResponse(service.list_tools(payload.get("connection") or payload))
        except InspectorError as exc:
            return _error_response(exc)

    @app.post("/api/tools/call")
    async def tools_call(request: Request) -> JSONResponse:
        try:
            payload = await _load_json(request)
            connection = payload.get("connection") or {}
            return JSONResponse(
                service.call_tool(
                    connection,
                    name=payload.get("name", ""),
                    arguments=payload.get("arguments") or {},
                )
            )
        except InspectorError as exc:
            return _error_response(exc)

    @app.post("/api/llm/openai/test")
    async def llm_openai_test(request: Request) -> JSONResponse:
        try:
            payload = await _load_json(request)
            connection = payload.get("connection") or {}
            return JSONResponse(
                service.run_openai_test(
                    connection,
                    api_key=str(payload.get("api_key") or ""),
                    model=str(payload.get("model") or ""),
                    prompt=str(payload.get("prompt") or ""),
                    system_prompt=payload.get("system_prompt"),
                    temperature=float(payload.get("temperature") or 0.2),
                    max_rounds=int(payload.get("max_rounds") or 4),
                )
            )
        except InspectorError as exc:
            return _error_response(exc)

    @app.post("/api/llm/openai/test/stream", response_model=None)
    async def llm_openai_test_stream(request: Request):
        try:
            payload = await _load_json(request)
            connection = payload.get("connection") or {}
        except InspectorError as exc:
            return _error_response(exc)

        def _stream():
            event_queue: "queue.Queue[str | None]" = queue.Queue()

            def emit(event: str, data: Dict[str, Any]) -> None:
                event_queue.put(_json_event(event, data))

            def run() -> None:
                try:
                    result = service.run_openai_test(
                        connection,
                        api_key=str(payload.get("api_key") or ""),
                        model=str(payload.get("model") or ""),
                        prompt=str(payload.get("prompt") or ""),
                        system_prompt=payload.get("system_prompt"),
                        temperature=float(payload.get("temperature") or 0.2),
                        max_rounds=int(payload.get("max_rounds") or 4),
                        event_sink=emit,
                    )
                    event_queue.put(_json_event("complete", result))
                except InspectorError as exc:
                    event_queue.put(_json_event("error", exc.to_dict()))
                finally:
                    event_queue.put(None)

            threading.Thread(target=run, daemon=True).start()
            yield _json_event("status", {"phase": "starting"})
            while True:
                chunk = event_queue.get()
                if chunk is None:
                    break
                yield chunk

        return StreamingResponse(_stream(), media_type="text/event-stream")

    return app


def run_inspector(
    *,
    host: str = "127.0.0.1",
    port: int = 9060,
    default_timeout: float = 8.0,
    open_browser: bool = True,
) -> None:
    app = create_app(default_timeout=default_timeout)
    url = f"http://{host}:{port}/"
    if open_browser:
        maybe_open_browser(url)
    uvicorn.run(app, host=host, port=port)
