"""Connection tester for MCP stdio/http transports."""
from __future__ import annotations

import json
import queue
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import urljoin

from ..protocol.mcp_jsonrpc import (
    MCP_METHOD_INITIALIZE,
    MCP_METHOD_TOOLS_CALL,
    MCP_METHOD_TOOLS_LIST,
    build_request,
)
from ..utils.logger import logger


@dataclass(slots=True)
class StepReport:
    name: str
    status: str
    duration_ms: float
    error: Optional[str] = None
    suggestion: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.error:
            payload["error"] = self.error
        if self.suggestion:
            payload["suggestion"] = self.suggestion
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(slots=True)
class ConnectionReport:
    mode: str
    target: Optional[str]
    steps: List[StepReport]
    duration_ms: float
    ok: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "target": self.target,
            "duration_ms": round(self.duration_ms, 2),
            "ok": self.ok,
            "steps": [step.to_dict() for step in self.steps],
        }


class StepFailure(Exception):
    def __init__(
        self,
        message: str,
        *,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.details = details or {}


class _StdioJsonRpcClient:
    def __init__(self, process: subprocess.Popen[str], timeout: float) -> None:
        self.process = process
        self.timeout = timeout
        self._stdout_queue: "queue.Queue[str]" = queue.Queue()
        self._stderr_lines: List[str] = []
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _read_stdout(self) -> None:
        if self.process.stdout is None:
            return
        for line in self.process.stdout:
            self._stdout_queue.put(line)

    def _read_stderr(self) -> None:
        if self.process.stderr is None:
            return
        for line in self.process.stderr:
            self._stderr_lines.append(line.rstrip())

    def send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.process.stdin is None:
            raise StepFailure("stdin 不可用", suggestion="請確認子程序支援 stdio 傳輸")
        try:
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except Exception as exc:
            raise StepFailure(
                "寫入 stdio 失敗",
                suggestion="請確認子程序仍在執行並可讀寫 stdin/stdout",
                details={"exception": str(exc)},
            ) from exc

        try:
            line = self._stdout_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise StepFailure(
                "等待回應逾時",
                suggestion="請確認 server 已回應 JSON-RPC 或提高 --timeout",
            ) from exc

        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise StepFailure(
                "回應不是合法 JSON",
                suggestion="請確認 server 回傳 JSON-RPC 格式",
                details={"raw": line.strip()},
            ) from exc

    def stderr_tail(self, max_lines: int = 10) -> str:
        if not self._stderr_lines:
            return ""
        return "\n".join(self._stderr_lines[-max_lines:])


class _SseClient:
    def __init__(self, stream, timeout: float) -> None:
        self.stream = stream
        self.timeout = timeout
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._thread = threading.Thread(target=self._read_events, daemon=True)
        self._thread.start()

    def _read_events(self) -> None:
        event = None
        data_lines: List[str] = []
        while True:
            line = self.stream.readline()
            if not line:
                break
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            line = line.rstrip("\n")
            if not line:
                if data_lines:
                    payload = "\n".join(data_lines)
                    try:
                        data = json.loads(payload)
                        self._queue.put({"event": event or "message", "data": data})
                    except json.JSONDecodeError:
                        logger.warning("SSE payload 解析失敗: %s", payload)
                event = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())

    def next_message(self) -> Dict[str, Any]:
        try:
            return self._queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise StepFailure(
                "等待 SSE 回應逾時",
                suggestion="請確認 server SSE 通道正常或提高 --timeout",
            ) from exc


class ConnectionTester:
    def __init__(self, *, timeout: float = 8.0) -> None:
        self.timeout = timeout

    def run_stdio(self, cmd: List[str]) -> ConnectionReport:
        start_time = time.monotonic()
        steps: List[StepReport] = []
        process: subprocess.Popen[str] | None = None
        client: _StdioJsonRpcClient | None = None
        tools_payload: List[Dict[str, Any]] = []

        def add_step(name: str, func) -> None:
            step_start = time.monotonic()
            try:
                details = func() or {}
                steps.append(
                    StepReport(
                        name=name,
                        status="PASS",
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        details=details,
                    )
                )
            except StepFailure as exc:
                logger.error("Doctor step %s failed: %s", name, exc.message)
                steps.append(
                    StepReport(
                        name=name,
                        status="FAIL",
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        error=exc.message,
                        suggestion=exc.suggestion,
                        details=exc.details,
                    )
                )
            except Exception as exc:
                logger.exception("Doctor step %s unexpected error", name)
                steps.append(
                    StepReport(
                        name=name,
                        status="FAIL",
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        error="未預期錯誤",
                        suggestion="請查看 logs/toolanything.log 取得細節",
                        details={"exception": str(exc)},
                    )
                )

        def start_process() -> Dict[str, Any]:
            nonlocal process, client
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise StepFailure(
                    "找不到啟動命令",
                    suggestion="請確認 --cmd 或 --tools 指定的指令路徑正確",
                    details={"command": " ".join(cmd)},
                ) from exc
            except Exception as exc:
                raise StepFailure(
                    "無法啟動 stdio server",
                    suggestion="請確認執行環境與權限",
                    details={"exception": str(exc)},
                ) from exc

            time.sleep(0.1)
            if process.poll() is not None:
                stderr = ""
                if process.stderr is not None:
                    stderr = process.stderr.read().strip()
                raise StepFailure(
                    "stdio server 啟動後立即結束",
                    suggestion="請確認 server 模組可正常執行",
                    details={"stderr": stderr},
                )
            client = _StdioJsonRpcClient(process, self.timeout)
            return {"pid": process.pid}

        def call_initialize() -> Dict[str, Any]:
            if client is None:
                raise StepFailure("stdio client 尚未建立")
            payload = build_request(MCP_METHOD_INITIALIZE, 1)
            response = client.send_request(payload)
            return _validate_response(response, 1)

        def call_tools_list() -> Dict[str, Any]:
            nonlocal tools_payload
            if client is None:
                raise StepFailure("stdio client 尚未建立")
            payload = build_request(MCP_METHOD_TOOLS_LIST, 2)
            response = client.send_request(payload)
            result = _validate_response(response, 2)
            tools_payload = result.get("tools", []) if isinstance(result, dict) else []
            return {"tools_count": len(tools_payload)}

        def call_tools_call() -> Dict[str, Any]:
            if client is None:
                raise StepFailure("stdio client 尚未建立")
            tool_name, arguments = _pick_callable_tool(tools_payload)
            if tool_name is None:
                raise StepFailure(
                    "找不到可穩定呼叫的工具",
                    suggestion="建議在工具模組中提供 __ping__ 或無必填參數的工具",
                )
            payload = build_request(
                MCP_METHOD_TOOLS_CALL,
                3,
                params={"name": tool_name, "arguments": arguments},
            )
            response = client.send_request(payload)
            _validate_response(response, 3)
            return {"tool": tool_name}

        add_step("transport", start_process)
        add_step("initialize", call_initialize)
        add_step("tools/list", call_tools_list)
        add_step("tools/call", call_tools_call)

        total_ms = (time.monotonic() - start_time) * 1000
        ok = all(step.status == "PASS" for step in steps)

        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        if client is not None and process is not None and process.poll() not in (None, 0):
            stderr = client.stderr_tail()
            if stderr:
                logger.warning("Doctor stdio stderr tail:\n%s", stderr)

        return ConnectionReport(
            mode="stdio",
            target=" ".join(cmd),
            steps=steps,
            duration_ms=total_ms,
            ok=ok,
        )

    def run_http(self, url: str) -> ConnectionReport:
        start_time = time.monotonic()
        steps: List[StepReport] = []
        tools_payload: List[Dict[str, Any]] = []
        sse_client: _SseClient | None = None
        message_endpoint: str | None = None

        def add_step(name: str, func) -> None:
            step_start = time.monotonic()
            try:
                details = func() or {}
                steps.append(
                    StepReport(
                        name=name,
                        status="PASS",
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        details=details,
                    )
                )
            except StepFailure as exc:
                logger.error("Doctor step %s failed: %s", name, exc.message)
                steps.append(
                    StepReport(
                        name=name,
                        status="FAIL",
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        error=exc.message,
                        suggestion=exc.suggestion,
                        details=exc.details,
                    )
                )
            except Exception as exc:
                logger.exception("Doctor step %s unexpected error", name)
                steps.append(
                    StepReport(
                        name=name,
                        status="FAIL",
                        duration_ms=(time.monotonic() - step_start) * 1000,
                        error="未預期錯誤",
                        suggestion="請查看 logs/toolanything.log 取得細節",
                        details={"exception": str(exc)},
                    )
                )

        def connect_transport() -> Dict[str, Any]:
            nonlocal sse_client, message_endpoint
            health_url = urljoin(url, "/health")
            try:
                with url_request.urlopen(health_url, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise StepFailure(
                            "health check 失敗",
                            suggestion="請確認 server 是否可連線",
                            details={"status": response.status},
                        )
            except url_error.HTTPError as exc:
                raise StepFailure(
                    "health check 失敗",
                    suggestion="請確認 server /health 是否可用",
                    details={"status": exc.code},
                ) from exc
            except url_error.URLError as exc:
                raise StepFailure(
                    "HTTP 連線失敗",
                    suggestion="請確認 URL 或 server 是否啟動",
                    details={"reason": str(exc.reason)},
                ) from exc

            sse_url = urljoin(url, "/sse")
            try:
                stream = url_request.urlopen(sse_url, timeout=self.timeout)
            except Exception as exc:
                raise StepFailure(
                    "SSE 連線失敗",
                    suggestion="請確認 /sse 端點是否可用",
                    details={"exception": str(exc)},
                ) from exc

            sse_client = _SseClient(stream, self.timeout)
            message = sse_client.next_message()
            payload = message.get("data", {})
            transport = payload.get("transport", {}) if isinstance(payload, dict) else {}
            endpoint = transport.get("messageEndpoint")
            if not endpoint:
                raise StepFailure(
                    "無法取得 MCP message endpoint",
                    suggestion="請確認 /sse 回傳格式",
                    details={"payload": payload},
                )
            message_endpoint = urljoin(url, endpoint)
            return {"message_endpoint": message_endpoint}

        def http_initialize() -> Dict[str, Any]:
            if message_endpoint is None or sse_client is None:
                raise StepFailure("SSE 尚未建立")
            payload = build_request(MCP_METHOD_INITIALIZE, 1)
            _post_json(message_endpoint, payload, timeout=self.timeout)
            response = sse_client.next_message().get("data", {})
            return _validate_response(response, 1)

        def http_tools_list() -> Dict[str, Any]:
            nonlocal tools_payload
            if message_endpoint is None or sse_client is None:
                raise StepFailure("SSE 尚未建立")
            payload = build_request(MCP_METHOD_TOOLS_LIST, 2)
            _post_json(message_endpoint, payload, timeout=self.timeout)
            response = sse_client.next_message().get("data", {})
            result = _validate_response(response, 2)
            tools_payload = result.get("tools", []) if isinstance(result, dict) else []
            return {"tools_count": len(tools_payload)}

        def http_tools_call() -> Dict[str, Any]:
            if message_endpoint is None or sse_client is None:
                raise StepFailure("SSE 尚未建立")
            tool_name, arguments = _pick_callable_tool(tools_payload)
            if tool_name is None:
                raise StepFailure(
                    "找不到可穩定呼叫的工具",
                    suggestion="建議註冊 __ping__ 或無必填參數的工具",
                )
            payload = build_request(
                MCP_METHOD_TOOLS_CALL,
                3,
                params={"name": tool_name, "arguments": arguments},
            )
            _post_json(message_endpoint, payload, timeout=self.timeout)
            response = sse_client.next_message().get("data", {})
            _validate_response(response, 3)
            return {"tool": tool_name}

        add_step("transport", connect_transport)
        add_step("initialize", http_initialize)
        add_step("tools/list", http_tools_list)
        add_step("tools/call", http_tools_call)

        total_ms = (time.monotonic() - start_time) * 1000
        ok = all(step.status == "PASS" for step in steps)
        return ConnectionReport(
            mode="http",
            target=url,
            steps=steps,
            duration_ms=total_ms,
            ok=ok,
        )

    def build_config_error(self, *, mode: str, message: str, suggestion: str) -> ConnectionReport:
        step = StepReport(
            name="config",
            status="FAIL",
            duration_ms=0.0,
            error=message,
            suggestion=suggestion,
        )
        return ConnectionReport(
            mode=mode,
            target=None,
            steps=[step],
            duration_ms=0.0,
            ok=False,
        )


def _pick_callable_tool(tools_payload: Iterable[Dict[str, Any]]) -> tuple[Optional[str], Dict[str, Any]]:
    for tool in tools_payload:
        if tool.get("name") == "__ping__":
            return "__ping__", {}
    for tool in tools_payload:
        schema = tool.get("input_schema") or {}
        required = schema.get("required") or []
        if not required:
            return tool.get("name"), {}
    return None, {}


def _validate_response(response: Dict[str, Any], request_id: int) -> Dict[str, Any]:
    if response.get("id") != request_id:
        raise StepFailure(
            "回應 id 不一致",
            suggestion="請確認 MCP JSON-RPC 回應格式",
            details={"response": response},
        )
    if "error" in response:
        raise StepFailure(
            "MCP 回應錯誤",
            suggestion="請確認 server 是否支援此 method",
            details={"error": response.get("error")},
        )
    return response.get("result", {})


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = url_request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with url_request.urlopen(req, timeout=timeout) as response:
            if response.status >= 400:
                raise StepFailure(
                    "HTTP request 失敗",
                    suggestion="請確認 MCP server 端點是否可用",
                    details={"status": response.status},
                )
    except url_error.HTTPError as exc:
        raise StepFailure(
            "HTTP request 失敗",
            suggestion="請確認 MCP server 端點是否可用",
            details={"status": exc.code},
        ) from exc
    except url_error.URLError as exc:
        raise StepFailure(
            "HTTP 連線失敗",
            suggestion="請確認 URL 或 server 是否啟動",
            details={"reason": str(exc.reason)},
        ) from exc


def render_report(report: ConnectionReport) -> str:
    lines = [
        f"Connection Tester ({report.mode})",
        f"Target: {report.target or 'N/A'}",
        f"Total: {report.duration_ms:.2f}ms",
        "",
    ]
    for step in report.steps:
        lines.append(
            f"- {step.name}: {step.status} ({step.duration_ms:.2f}ms)"
        )
        if step.error:
            lines.append(f"  - error: {step.error}")
        if step.suggestion:
            lines.append(f"  - suggestion: {step.suggestion}")
        if step.details:
            lines.append(f"  - details: {json.dumps(step.details, ensure_ascii=False)}")
    return "\n".join(lines)


def parse_cmd(cmd: str) -> List[str]:
    return shlex.split(cmd)
