"""Dummy MCP Client，用以驗證 mcp_server_demo 是否可正常存取。"""
from __future__ import annotations

import json
import multiprocessing
import socket
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def _request_json(method: str, url: str, payload: Dict[str, Any] | None = None) -> Tuple[int, Dict[str, Any]]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=5) as resp:  # type: ignore[arg-type]
        return resp.status, json.loads(resp.read().decode("utf-8") or "{}")


def _wait_for_server(port: int, host: str, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    url = f"http://{host}:{port}/health"
    while time.time() < deadline:
        try:
            status, payload = _request_json("GET", url)
            if status == 200 and payload.get("status") == "ok":
                print(f"[dummy client] Server is ready: {payload}")
                return
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            time.sleep(0.2)
            continue
    raise RuntimeError("MCP Server 未在預期時間內就緒")


def _run_server_process(port: int, host: str) -> multiprocessing.Process:
    def _target() -> None:
        import server

        server.start_server(port=port, host=host)

    process = multiprocessing.Process(target=_target, daemon=True)
    process.start()
    return process


def main() -> None:
    host = "127.0.0.1"
    port = _find_free_port()
    print(f"[dummy client] 啟動範例 MCP Server，port={port}")

    server_process = _run_server_process(port, host)
    try:
        _wait_for_server(port, host)

        print("[dummy client] 1) 列出工具列表：")
        status, tools_payload = _request_json("GET", f"http://{host}:{port}/tools")
        print(f"HTTP {status}\n{json.dumps(tools_payload, ensure_ascii=False, indent=2)}")

        print("[dummy client] 2) 呼叫 echo.text：")
        status, invoke_payload = _request_json(
            "POST",
            f"http://{host}:{port}/invoke",
            payload={"name": "echo.text", "arguments": {"text": "Hello MCP"}},
        )
        print(f"HTTP {status}\n{json.dumps(invoke_payload, ensure_ascii=False, indent=2)}")

    finally:
        print("[dummy client] 結束並停止範例 MCP Server。")
        server_process.terminate()
        server_process.join(timeout=2)


if __name__ == "__main__":
    main()
