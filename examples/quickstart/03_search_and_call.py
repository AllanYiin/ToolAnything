"""Quickstart: tools/list → CLI search → tools/call。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from toolanything.cli import main as cli_main
from toolanything.protocol.mcp_jsonrpc import (
    MCP_METHOD_INITIALIZE,
    MCP_METHOD_NOTIFICATIONS_INITIALIZED,
    MCP_METHOD_TOOLS_CALL,
    MCP_METHOD_TOOLS_LIST,
    build_notification,
    build_request,
)
from toolanything.runtime.serve import load_tool_module


def _send(proc: subprocess.Popen[str], payload: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _read_line(proc: subprocess.Popen[str]) -> str:
    assert proc.stdout is not None
    return proc.stdout.readline().strip()


def _run_cli_search(args: Iterable[str]) -> None:
    original = sys.argv[:]
    sys.argv = ["toolanything", "search", *args]
    try:
        cli_main()
    finally:
        sys.argv = original


def main() -> None:
    module_path = Path(__file__).with_name("01_define_tools.py")
    load_tool_module(str(module_path))

    print("[1] CLI search（允許 side_effect）")
    _run_cli_search(["--query", "quickstart", "--top-k", "5", "--allow-side-effects"])

    print("\n[2] MCP tools/list 與 tools/call（stdio）")
    cmd = [
        sys.executable,
        "-m",
        "toolanything.cli",
        "serve",
        str(module_path),
        "--stdio",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        _send(proc, build_request(MCP_METHOD_INITIALIZE, 1))
        print("initialize:", _read_line(proc))

        _send(proc, build_notification(MCP_METHOD_NOTIFICATIONS_INITIALIZED, {}))

        _send(proc, build_request(MCP_METHOD_TOOLS_LIST, 2))
        print("tools/list:", _read_line(proc))

        _send(
            proc,
            build_request(
                MCP_METHOD_TOOLS_CALL,
                3,
                params={"name": "quickstart.add", "arguments": {"a": 2, "b": 3}},
            ),
        )
        print("tools/call:", _read_line(proc))
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()

# 預期輸出片段（實際內容會包含 JSON）：
# [1] CLI search（允許 side_effect）
# {"name": "quickstart.greet", ...}
# {"name": "quickstart.add", ...}
# {"name": "quickstart.store_note", ...}
#
# [2] MCP tools/list 與 tools/call（stdio）
# initialize: {"jsonrpc": "2.0", "id": 1, "result": ...}
# tools/list: {"jsonrpc": "2.0", "id": 2, "result": {"tools": [...]}}
# tools/call: {"jsonrpc": "2.0", "id": 3, "result": ...}
