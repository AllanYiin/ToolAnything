from __future__ import annotations

import http.client
import json
import socket
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

REPO_SRC = Path(__file__).resolve().parents[2] / "src"
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

from toolanything import tool
from toolanything.core.registry import ToolRegistry
from toolanything.server.mcp_streamable_http import (
    MCP_PROTOCOL_VERSION_HEADER,
    MCP_SESSION_ID_HEADER,
    _build_handler as build_streamable_handler,
)


HOST = "127.0.0.1"
DEFAULT_PROTOCOL_VERSION = "2025-11-25"


@dataclass(slots=True)
class DemoServer:
    server: ThreadingHTTPServer
    thread: threading.Thread

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{HOST}:{self.port}"

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @tool(name="audio.pipeline.status", description="回報音訊前處理管線狀態", registry=registry)
    def pipeline_status() -> dict[str, Any]:
        return {
            "pipeline": ["vad_gate", "asr_preview"],
            "preferred_transport": "streamable_http",
            "note": "先用 VAD 判斷是否有語音，再決定是否進入 ASR。",
        }

    @tool(name="audio.vad.inspect_chunk", description="判斷片段是否要送往 ASR", registry=registry)
    def inspect_chunk(
        chunk_label: str,
        avg_energy: float,
        speech_band_ratio: float,
        noise_floor: float = 0.12,
    ) -> dict[str, Any]:
        vad_score = round((avg_energy * 0.62) + (speech_band_ratio * 0.58) - (noise_floor * 0.7), 4)
        speech_detected = vad_score >= 0.45
        return {
            "chunk_label": chunk_label,
            "vad_score": vad_score,
            "speech_detected": speech_detected,
            "route": "forward_to_asr" if speech_detected else "skip_chunk",
            "explanation": (
                "疑似連續語音，建議送到下一段 ASR。"
                if speech_detected
                else "較像停頓或背景底噪，可以先略過。"
            ),
        }

    @tool(name="audio.asr.preview_transcript", description="模擬通過 VAD 後的 ASR 預覽", registry=registry)
    def preview_transcript(
        chunk_label: str,
        route: str,
        speaker_hint: str = "operator",
    ) -> dict[str, Any]:
        accepted = route == "forward_to_asr"
        return {
            "chunk_label": chunk_label,
            "accepted": accepted,
            "speaker_hint": speaker_hint,
            "transcript_preview": (
                "toolanything request a systems check"
                if accepted
                else ""
            ),
            "next_stage": "whisper_or_other_asr" if accepted else "skipped",
        }

    return registry


@contextmanager
def running_demo_server() -> Iterator[DemoServer]:
    registry = _build_registry()
    base_handler_cls = build_streamable_handler(registry, host=HOST, port=0)

    class QuietStreamableHandler(base_handler_cls):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            del format, args

    server = ThreadingHTTPServer((HOST, 0), QuietStreamableHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    demo_server = DemoServer(server=server, thread=thread)
    try:
        yield demo_server
    finally:
        demo_server.shutdown()


def _streamable_headers(
    *,
    accept: str,
    session_id: str | None = None,
    protocol_version: str | None = None,
) -> dict[str, str]:
    headers = {"Accept": accept}
    if session_id or accept != "text/event-stream":
        headers["Content-Type"] = "application/json"
    if session_id:
        headers[MCP_SESSION_ID_HEADER] = session_id
    if protocol_version:
        headers[MCP_PROTOCOL_VERSION_HEADER] = protocol_version
    return headers


def _request_json(
    *,
    port: int,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    conn = http.client.HTTPConnection(HOST, port, timeout=5)
    try:
        body = json.dumps(payload, ensure_ascii=False) if payload is not None else None
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        response_headers = {key: value for key, value in response.getheaders()}
        raw_body = response.read().decode("utf-8")
        parsed_body = json.loads(raw_body or "{}") if raw_body else {}
        return response.status, response_headers, parsed_body
    finally:
        conn.close()


def initialize_session(port: int) -> dict[str, Any]:
    status, headers, body = _request_json(
        port=port,
        method="POST",
        path="/mcp",
        payload={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": DEFAULT_PROTOCOL_VERSION},
        },
        headers=_streamable_headers(
            accept="application/json",
            protocol_version=DEFAULT_PROTOCOL_VERSION,
        ),
    )
    return {
        "status": status,
        "headers": headers,
        "body": body,
        "session_id": headers.get(MCP_SESSION_ID_HEADER),
        "protocol_version": headers.get(MCP_PROTOCOL_VERSION_HEADER),
    }


def list_tools(port: int, *, session_id: str, protocol_version: str) -> dict[str, Any]:
    status, _, body = _request_json(
        port=port,
        method="POST",
        path="/mcp",
        payload={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        headers=_streamable_headers(
            accept="application/json",
            session_id=session_id,
            protocol_version=protocol_version,
        ),
    )
    return {"status": status, "body": body}


def call_tool_json(
    port: int,
    *,
    session_id: str,
    protocol_version: str,
    request_id: int,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    status, _, body = _request_json(
        port=port,
        method="POST",
        path="/mcp",
        payload={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        },
        headers=_streamable_headers(
            accept="application/json",
            session_id=session_id,
            protocol_version=protocol_version,
        ),
    )
    return {"status": status, "body": body}


def call_tool_stream(
    port: int,
    *,
    session_id: str,
    protocol_version: str,
    request_id: int,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    conn = http.client.HTTPConnection(HOST, port, timeout=5)
    try:
        conn.request(
            "POST",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
                ensure_ascii=False,
            ),
            headers=_streamable_headers(
                accept="text/event-stream",
                session_id=session_id,
                protocol_version=protocol_version,
            ),
        )
        response = conn.getresponse()
        events = [_read_sse_event(response), _read_sse_event(response)]
        return {
            "status": response.status,
            "content_type": response.getheader("Content-Type"),
            "events": events,
        }
    finally:
        conn.close()


def open_ready_stream(
    port: int,
    *,
    session_id: str,
    protocol_version: str,
    last_event_id: int | None = None,
    timeout_sec: float = 5.0,
) -> dict[str, Any]:
    conn = http.client.HTTPConnection(HOST, port, timeout=timeout_sec)
    headers = {
        "Accept": "text/event-stream",
        MCP_SESSION_ID_HEADER: session_id,
        MCP_PROTOCOL_VERSION_HEADER: protocol_version,
    }
    if last_event_id is not None:
        headers["Last-Event-ID"] = str(last_event_id)

    conn.request("GET", "/mcp", headers=headers)
    response = conn.getresponse()
    return {
        "connection": conn,
        "response": response,
    }


def delete_session(port: int, *, session_id: str, protocol_version: str) -> dict[str, Any]:
    status, _, body = _request_json(
        port=port,
        method="DELETE",
        path="/mcp",
        headers=_streamable_headers(
            accept="application/json",
            session_id=session_id,
            protocol_version=protocol_version,
        ),
    )
    return {"status": status, "body": body}


def run_handshake_demo() -> dict[str, Any]:
    with running_demo_server() as demo:
        initialized = initialize_session(demo.port)
        session_id = str(initialized["session_id"])
        protocol_version = str(initialized["protocol_version"])
        tools = list_tools(demo.port, session_id=session_id, protocol_version=protocol_version)

        vad_call = call_tool_json(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
            request_id=3,
            tool_name="audio.vad.inspect_chunk",
            arguments={
                "chunk_label": "segment-01",
                "avg_energy": 0.91,
                "speech_band_ratio": 0.79,
                "noise_floor": 0.11,
            },
        )
        vad_result = vad_call["body"].get("raw_result", {})
        asr_call = call_tool_json(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
            request_id=4,
            tool_name="audio.asr.preview_transcript",
            arguments={
                "chunk_label": "segment-01",
                "route": vad_result.get("route", "skip_chunk"),
                "speaker_hint": "tower",
            },
        )
        return {
            "story": "同一個 Streamable HTTP session 先做 VAD，再決定是否把片段送往 ASR 預覽。",
            "server_url": demo.base_url,
            "initialize": initialized,
            "tools": tools["body"].get("result", {}).get("tools", []),
            "vad_result": vad_result,
            "asr_result": asr_call["body"].get("raw_result", {}),
        }


def run_response_mode_demo() -> dict[str, Any]:
    with running_demo_server() as demo:
        initialized = initialize_session(demo.port)
        session_id = str(initialized["session_id"])
        protocol_version = str(initialized["protocol_version"])
        vad_gate = call_tool_json(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
            request_id=3,
            tool_name="audio.vad.inspect_chunk",
            arguments={
                "chunk_label": "segment-02",
                "avg_energy": 0.88,
                "speech_band_ratio": 0.74,
                "noise_floor": 0.12,
            },
        )
        route = vad_gate["body"].get("raw_result", {}).get("route", "skip_chunk")
        asr_arguments = {
            "chunk_label": "segment-02",
            "route": route,
            "speaker_hint": "operator",
        }
        json_result = call_tool_json(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
            request_id=4,
            tool_name="audio.asr.preview_transcript",
            arguments=asr_arguments,
        )
        stream_result = call_tool_stream(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
            request_id=5,
            tool_name="audio.asr.preview_transcript",
            arguments=asr_arguments,
        )
        return {
            "story": "VAD 先決定片段可不可以進 ASR；接著同一個 ASR preview call 既可以回 JSON，也可以回 stream。",
            "vad_gate": vad_gate,
            "json_mode": json_result,
            "stream_mode": stream_result,
        }


def run_session_resume_demo() -> dict[str, Any]:
    with running_demo_server() as demo:
        initialized = initialize_session(demo.port)
        session_id = str(initialized["session_id"])
        protocol_version = str(initialized["protocol_version"])

        first_stream = open_ready_stream(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
        )
        try:
            ready_event = _read_sse_event(first_stream["response"])
        finally:
            first_stream["connection"].close()

        replay_stream = open_ready_stream(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
            last_event_id=int(ready_event.get("id") or 0),
            timeout_sec=1.0,
        )
        try:
            replay_event = _try_read_sse_event(replay_stream["response"], timeout_sec=0.4)
        finally:
            replay_stream["connection"].close()

        deleted = delete_session(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
        )
        missing = list_tools(
            demo.port,
            session_id=session_id,
            protocol_version=protocol_version,
        )
        return {
            "story": "如果你的 VAD -> ASR client 斷線，GET /mcp 可重新接上；DELETE /mcp 則會回收整個 session。",
            "ready_event": ready_event,
            "replay_after_last_event_id": replay_event,
            "delete_result": deleted,
            "after_delete": missing,
        }


def pretty_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _read_sse_event(response: http.client.HTTPResponse) -> dict[str, Any]:
    event: dict[str, Any] = {}
    data_lines: list[str] = []
    while True:
        line = response.fp.readline().decode("utf-8")
        if line == "":
            raise EOFError("stream closed before receiving a complete SSE event")
        stripped = line.rstrip("\n")
        if stripped == "":
            break
        if stripped.startswith("id: "):
            event["id"] = int(stripped[4:])
        elif stripped.startswith("event: "):
            event["event"] = stripped[7:]
        elif stripped.startswith("data: "):
            data_lines.append(stripped[6:])
    event["data"] = json.loads("\n".join(data_lines)) if data_lines else {}
    return event


def _try_read_sse_event(
    response: http.client.HTTPResponse,
    *,
    timeout_sec: float,
) -> dict[str, Any] | None:
    raw_socket = getattr(getattr(response.fp, "raw", None), "_sock", None)
    if raw_socket is None:
        return None
    previous_timeout = raw_socket.gettimeout()
    raw_socket.settimeout(timeout_sec)
    try:
        return _read_sse_event(response)
    except (OSError, socket.timeout, EOFError):
        return None
    finally:
        raw_socket.settimeout(previous_timeout)
