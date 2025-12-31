"""Run MCP stdio roundtrip for initialize/tools/list/tools/call."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from toolanything.protocol.mcp_jsonrpc import (
    MCP_METHOD_INITIALIZE,
    MCP_METHOD_NOTIFICATIONS_INITIALIZED,
    MCP_METHOD_TOOLS_CALL,
    MCP_METHOD_TOOLS_LIST,
    build_notification,
    build_request,
)


def _send(proc: subprocess.Popen[str], payload: dict) -> None:
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _read(proc: subprocess.Popen[str]) -> dict:
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("未收到 MCP 回應")
    return json.loads(line)


def main() -> None:
    module_path = Path(__file__).resolve().parent / "tools.py"
    cmd = [
        sys.executable,
        "-m",
        "toolanything.cli",
        "serve",
        str(module_path),
        "--stdio",
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("無法啟動 MCP stdio server")

    try:
        _send(proc, build_request(MCP_METHOD_INITIALIZE, 1))
        init_response = _read(proc)
        print("initialize:", json.dumps(init_response, ensure_ascii=False))

        _send(proc, build_notification(MCP_METHOD_NOTIFICATIONS_INITIALIZED, {}))

        _send(proc, build_request(MCP_METHOD_TOOLS_LIST, 2))
        tools_response = _read(proc)
        print("tools/list:", json.dumps(tools_response, ensure_ascii=False))

        _send(
            proc,
            build_request(
                MCP_METHOD_TOOLS_CALL,
                3,
                params={
                    "name": "calculator.add",
                    "arguments": {"a": 7, "b": 5},
                },
            ),
        )
        call_response = _read(proc)
        print("tools/call:", json.dumps(call_response, ensure_ascii=False))
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
