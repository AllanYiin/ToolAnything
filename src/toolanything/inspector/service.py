"""Backend service for the built-in MCP inspector."""
from __future__ import annotations

import json
import subprocess
import threading
import time
import webbrowser
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import urlencode, urljoin

from ..core.connection_tester import (
    ConnectionTester,
    StepFailure,
    _SseClient,
    _StdioJsonRpcClient,
    parse_cmd,
)
from ..protocol.mcp_jsonrpc import (
    MCP_METHOD_INITIALIZE,
    MCP_METHOD_NOTIFICATIONS_INITIALIZED,
    MCP_METHOD_TOOLS_CALL,
    MCP_METHOD_TOOLS_LIST,
    build_notification,
    build_request,
)


class InspectorError(Exception):
    """Base error for inspector service failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload = {"message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class MCPResponseError(InspectorError):
    """Raised when the target MCP server returns a JSON-RPC error."""


@dataclass(slots=True)
class ConnectionConfig:
    mode: str
    timeout: float = 8.0
    url: Optional[str] = None
    command: Optional[str] = None
    user_id: Optional[str] = None


@dataclass(slots=True)
class TraceEntry:
    direction: str
    kind: str
    payload: Dict[str, Any]
    transport: str
    at_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "kind": self.kind,
            "payload": self.payload,
            "transport": self.transport,
            "at_ms": round(self.at_ms, 2),
        }


def _normalize_config(payload: Mapping[str, Any]) -> ConnectionConfig:
    mode = str(payload.get("mode") or "").strip().lower()
    timeout = float(payload.get("timeout") or 8.0)
    user_id = str(payload.get("user_id") or "").strip() or None

    if mode not in {"http", "stdio"}:
        raise InspectorError("mode 僅支援 http 或 stdio")

    if timeout <= 0:
        raise InspectorError("timeout 必須大於 0")

    if mode == "http":
        url = str(payload.get("url") or "").strip()
        if not url:
            raise InspectorError("http 模式缺少 url")
        return ConnectionConfig(
            mode=mode,
            timeout=timeout,
            url=url.rstrip("/"),
            user_id=user_id,
        )

    command = str(payload.get("command") or "").strip()
    if not command:
        raise InspectorError("stdio 模式缺少 command")
    return ConnectionConfig(
        mode=mode,
        timeout=timeout,
        command=command,
        user_id=user_id,
    )


def _unwrap_response(response: Dict[str, Any], request_id: int) -> Dict[str, Any]:
    if response.get("id") != request_id:
        raise InspectorError(
            "MCP 回應 id 不一致",
            status_code=502,
            details={"response": response, "expected_id": request_id},
        )

    if "error" in response:
        error_payload = response.get("error") or {}
        raise MCPResponseError(
            str(error_payload.get("message") or "MCP call 失敗"),
            status_code=400,
            details={"error": error_payload},
        )

    return response.get("result", {}) or {}


class _BaseInspectorSession(AbstractContextManager["_BaseInspectorSession"]):
    def __init__(self) -> None:
        self._request_id = 0
        self._started_at = time.monotonic()
        self.trace: list[TraceEntry] = []

    def __enter__(self) -> "_BaseInspectorSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        raise NotImplementedError

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _record(self, *, direction: str, kind: str, transport: str, payload: Dict[str, Any]) -> None:
        self.trace.append(
            TraceEntry(
                direction=direction,
                kind=kind,
                transport=transport,
                payload=payload,
                at_ms=(time.monotonic() - self._started_at) * 1000,
            )
        )

    def export_trace(self) -> list[Dict[str, Any]]:
        return [entry.to_dict() for entry in self.trace]

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _send_notification(self, payload: Dict[str, Any]) -> None:
        raise NotImplementedError

    def initialize(self) -> Dict[str, Any]:
        request_id = self._next_id()
        response = self._send_request(build_request(MCP_METHOD_INITIALIZE, request_id))
        result = _unwrap_response(response, request_id)
        self._send_notification(build_notification(MCP_METHOD_NOTIFICATIONS_INITIALIZED, {}))
        return result

    def list_tools(self) -> list[Dict[str, Any]]:
        request_id = self._next_id()
        response = self._send_request(build_request(MCP_METHOD_TOOLS_LIST, request_id))
        result = _unwrap_response(response, request_id)
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        request_id = self._next_id()
        response = self._send_request(
            build_request(
                MCP_METHOD_TOOLS_CALL,
                request_id,
                params={"name": name, "arguments": dict(arguments)},
            )
        )
        return _unwrap_response(response, request_id)


class _StdioInspectorSession(_BaseInspectorSession):
    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__()
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self.client: _StdioJsonRpcClient | None = None

    def __enter__(self) -> "_StdioInspectorSession":
        super().__enter__()
        try:
            self.process = subprocess.Popen(
                parse_cmd(self.config.command or ""),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise InspectorError(
                "找不到 stdio 啟動命令",
                details={"command": self.config.command},
            ) from exc
        except Exception as exc:
            raise InspectorError(
                "無法啟動 stdio server",
                details={"exception": str(exc), "command": self.config.command},
            ) from exc

        time.sleep(0.1)
        if self.process.poll() is not None:
            stderr = ""
            if self.process.stderr is not None:
                stderr = self.process.stderr.read().strip()
            raise InspectorError(
                "stdio server 啟動後立即結束",
                details={"stderr": stderr, "command": self.config.command},
            )

        self.client = _StdioJsonRpcClient(self.process, self.config.timeout)
        return self

    def close(self) -> None:
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.client is None:
            raise InspectorError("stdio client 尚未建立", status_code=500)
        try:
            self._record(direction="outbound", kind="request", transport="stdio", payload=payload)
            response = self.client.send_request(payload)
            self._record(direction="inbound", kind="response", transport="stdio", payload=response)
            return response
        except StepFailure as exc:
            raise InspectorError(
                exc.message,
                details={"suggestion": exc.suggestion, **exc.details},
            ) from exc

    def _send_notification(self, payload: Dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise InspectorError("stdio client 尚未建立", status_code=500)
        try:
            self._record(direction="outbound", kind="notification", transport="stdio", payload=payload)
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except Exception as exc:
            raise InspectorError(
                "寫入 stdio notification 失敗",
                details={"exception": str(exc)},
            ) from exc


class _HttpInspectorSession(_BaseInspectorSession):
    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__()
        self.config = config
        self.stream = None
        self.sse_client: _SseClient | None = None
        self.message_endpoint: str | None = None

    def __enter__(self) -> "_HttpInspectorSession":
        super().__enter__()
        health_url = urljoin(f"{self.config.url}/", "health")
        try:
            with url_request.urlopen(health_url, timeout=self.config.timeout) as response:
                if response.status >= 400:
                    raise InspectorError(
                        "health check 失敗",
                        details={"status": response.status, "url": health_url},
                    )
        except url_error.URLError as exc:
            raise InspectorError(
                "HTTP 連線失敗",
                details={"reason": str(getattr(exc, "reason", exc)), "url": self.config.url},
            ) from exc

        sse_url = urljoin(f"{self.config.url}/", "sse")
        if self.config.user_id:
            sse_url = f"{sse_url}?{urlencode({'user_id': self.config.user_id})}"
        try:
            self.stream = url_request.urlopen(sse_url, timeout=self.config.timeout)
        except Exception as exc:
            raise InspectorError(
                "SSE 連線失敗",
                details={"exception": str(exc), "url": sse_url},
            ) from exc

        self.sse_client = _SseClient(self.stream, self.config.timeout)
        transport_message = self._next_transport_ready()
        transport_payload = transport_message.get("params", {}).get("transport") or transport_message.get(
            "transport", {}
        )
        endpoint = transport_payload.get("messageEndpoint")
        if not endpoint:
            raise InspectorError(
                "無法取得 MCP message endpoint",
                status_code=502,
                details={"payload": transport_message},
            )
        self.message_endpoint = urljoin(f"{self.config.url}/", endpoint.lstrip("/"))
        return self

    def close(self) -> None:
        if self.stream is not None:
            try:
                self.stream.close()
            except Exception:
                pass

    def _next_transport_ready(self) -> Dict[str, Any]:
        if self.sse_client is None:
            raise InspectorError("SSE 尚未建立", status_code=500)
        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            try:
                event = self.sse_client.next_message()
            except StepFailure as exc:
                raise InspectorError(exc.message, details={"suggestion": exc.suggestion}) from exc
            if event.get("event") == "ping":
                continue
            payload = event.get("data", {})
            if isinstance(payload, dict) and payload.get("method") == "transport/ready":
                self._record(direction="inbound", kind="event", transport="http", payload=payload)
                return payload
        raise InspectorError("等待 transport/ready 逾時", status_code=504)

    def _next_response(self, request_id: int) -> Dict[str, Any]:
        if self.sse_client is None:
            raise InspectorError("SSE 尚未建立", status_code=500)
        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            try:
                event = self.sse_client.next_message()
            except StepFailure as exc:
                raise InspectorError(exc.message, details={"suggestion": exc.suggestion}) from exc
            if event.get("event") == "ping":
                continue
            payload = event.get("data", {})
            if isinstance(payload, dict) and payload.get("id") == request_id:
                self._record(direction="inbound", kind="response", transport="http", payload=payload)
                return payload
        raise InspectorError(
            "等待 MCP 回應逾時",
            status_code=504,
            details={"request_id": request_id},
        )

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.message_endpoint is None:
            raise InspectorError("message endpoint 尚未建立", status_code=500)
        self._record(direction="outbound", kind="request", transport="http", payload=payload)
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = url_request.Request(
                self.message_endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with url_request.urlopen(req, timeout=self.config.timeout) as response:
                if response.status >= 400:
                    raise InspectorError(
                        "HTTP request 失敗",
                        details={"status": response.status, "endpoint": self.message_endpoint},
                    )
        except url_error.HTTPError as exc:
            raise InspectorError(
                "HTTP request 失敗",
                details={"status": exc.code, "endpoint": self.message_endpoint},
            ) from exc
        except url_error.URLError as exc:
            raise InspectorError(
                "HTTP 連線失敗",
                details={"reason": str(getattr(exc, "reason", exc)), "endpoint": self.message_endpoint},
            ) from exc
        return self._next_response(int(payload["id"]))

    def _send_notification(self, payload: Dict[str, Any]) -> None:
        if self.message_endpoint is None:
            raise InspectorError("message endpoint 尚未建立", status_code=500)
        self._record(direction="outbound", kind="notification", transport="http", payload=payload)
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = url_request.Request(
                self.message_endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with url_request.urlopen(req, timeout=self.config.timeout):
                return
        except Exception as exc:
            raise InspectorError(
                "送出 notification 失敗",
                details={"exception": str(exc), "endpoint": self.message_endpoint},
            ) from exc


class MCPInspectorService:
    """Service layer for the built-in MCP test client."""

    def __init__(self, *, default_timeout: float = 8.0) -> None:
        self.default_timeout = default_timeout

    def _build_config(self, payload: Mapping[str, Any]) -> ConnectionConfig:
        normalized = dict(payload)
        normalized.setdefault("timeout", self.default_timeout)
        return _normalize_config(normalized)

    def _open_session(self, config: ConnectionConfig) -> _BaseInspectorSession:
        if config.mode == "stdio":
            return _StdioInspectorSession(config)
        return _HttpInspectorSession(config)

    def test_connection(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        config = self._build_config(payload)
        tester = ConnectionTester(timeout=config.timeout)
        if config.mode == "stdio":
            report = tester.run_stdio(parse_cmd(config.command or ""))
        else:
            report = tester.run_http(config.url or "")
        return report.to_dict()

    def list_tools(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        config = self._build_config(payload)
        with self._open_session(config) as session:
            initialize = session.initialize()
            tools = session.list_tools()
        return {
            "mode": config.mode,
            "target": config.url if config.mode == "http" else config.command,
            "initialize": initialize,
            "tools": tools,
            "count": len(tools),
            "trace": session.export_trace(),
        }

    def call_tool(
        self,
        payload: Mapping[str, Any],
        *,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        tool_name = str(name or "").strip()
        if not tool_name:
            raise InspectorError("缺少工具名稱")
        config = self._build_config(payload)
        with self._open_session(config) as session:
            session.initialize()
            result = session.call_tool(tool_name, arguments or {})
        return {
            "mode": config.mode,
            "target": config.url if config.mode == "http" else config.command,
            "tool": tool_name,
            "arguments": dict(arguments or {}),
            "result": result,
            "trace": session.export_trace(),
        }

    def run_openai_test(
        self,
        payload: Mapping[str, Any],
        *,
        api_key: str,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_rounds: int = 4,
        event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if not api_key.strip():
            raise InspectorError("缺少 OpenAI API key")
        if not model.strip():
            raise InspectorError("缺少 model")
        if not prompt.strip():
            raise InspectorError("缺少 prompt")
        if max_rounds < 1:
            raise InspectorError("max_rounds 必須大於 0")

        config = self._build_config(payload)
        with self._open_session(config) as session:
            session.initialize()
            tools = session.list_tools()
            messages: list[Dict[str, Any]] = []
            transcript: list[Dict[str, Any]] = []
            final_text = ""

            if system_prompt and system_prompt.strip():
                messages.append({"role": "system", "content": system_prompt.strip()})
            messages.append({"role": "user", "content": prompt.strip()})
            transcript.append({"role": "user", "content": prompt.strip()})
            self._emit(event_sink, "status", {"phase": "planning", "tools_count": len(tools)})

            for _ in range(max_rounds):
                assistant_message = self._request_openai_chat_completion(
                    api_key=api_key,
                    model=model.strip(),
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                )

                content = assistant_message.get("content")
                tool_calls = assistant_message.get("tool_calls") or []
                transcript.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    }
                )
                if tool_calls:
                    self._emit(event_sink, "assistant", {"tool_calls": tool_calls, "content": content})
                    messages.append(
                        {
                            "role": "assistant",
                            "content": content,
                            "tool_calls": tool_calls,
                        }
                    )
                    for tool_call in tool_calls:
                        function = tool_call.get("function") or {}
                        tool_name = function.get("name")
                        arguments_text = function.get("arguments") or "{}"
                        try:
                            tool_arguments = json.loads(arguments_text)
                        except json.JSONDecodeError as exc:
                            raise InspectorError(
                                "OpenAI 回傳的工具參數不是合法 JSON",
                                status_code=502,
                                details={"arguments": arguments_text, "tool": tool_name},
                            ) from exc

                        result = session.call_tool(tool_name, tool_arguments)
                        result_text = json.dumps(result, ensure_ascii=False)
                        tool_entry = {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id"),
                            "name": tool_name,
                            "arguments": tool_arguments,
                            "content": result_text,
                            "result": result,
                        }
                        transcript.append(tool_entry)
                        self._emit(event_sink, "tool", tool_entry)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.get("id"),
                                "content": result_text,
                            }
                        )
                    continue

                final_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                self._emit(event_sink, "assistant", {"content": final_text, "done": True})
                break
            else:
                raise InspectorError(
                    "超過 LLM 工具呼叫輪數上限",
                    status_code=502,
                    details={"max_rounds": max_rounds},
                )

        return {
            "mode": config.mode,
            "target": config.url if config.mode == "http" else config.command,
            "model": model.strip(),
            "tools_count": len(tools),
            "final_text": final_text,
            "transcript": transcript,
            "trace": session.export_trace(),
        }

    def _request_openai_chat_completion(
        self,
        *,
        api_key: str,
        model: str,
        messages: list[Dict[str, Any]],
        tools: list[Dict[str, Any]],
        temperature: float,
    ) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
                for tool in tools
            ],
            "tool_choice": "auto",
            "temperature": temperature,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = url_request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with url_request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
        except url_error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            details: Dict[str, Any] = {"status": exc.code}
            try:
                details["response"] = json.loads(raw_body)
            except json.JSONDecodeError:
                details["response_text"] = raw_body
            raise InspectorError("OpenAI API 呼叫失敗", status_code=502, details=details) from exc
        except url_error.URLError as exc:
            raise InspectorError(
                "OpenAI API 連線失敗",
                status_code=502,
                details={"reason": str(getattr(exc, "reason", exc))},
            ) from exc

        choices = body.get("choices") or []
        if not choices:
            raise InspectorError(
                "OpenAI API 未回傳 choices",
                status_code=502,
                details={"response": body},
            )
        message = choices[0].get("message") or {}
        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
        }

    @staticmethod
    def _emit(
        event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
        event: str,
        payload: Dict[str, Any],
    ) -> None:
        if event_sink is not None:
            event_sink(event, payload)


def maybe_open_browser(url: str, *, delay_seconds: float = 0.6) -> None:
    """Open the inspector in a browser after the local server starts."""

    def _open() -> None:
        time.sleep(delay_seconds)
        try:
            webbrowser.open(url)
        except Exception:
            return

    threading.Thread(target=_open, daemon=True).start()
