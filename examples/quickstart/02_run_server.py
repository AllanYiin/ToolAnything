"""Quickstart: 啟動 MCP stdio transport（最少參數）。"""
from __future__ import annotations

from pathlib import Path

from toolanything.runtime.serve import load_tool_module
from toolanything.server.mcp_stdio_server import run_stdio_server


if __name__ == "__main__":
    print("[Quickstart] MCP stdio server 已啟動，等待 JSON-RPC 訊息…")
    module_path = Path(__file__).with_name("01_define_tools.py")
    load_tool_module(str(module_path))
    run_stdio_server()
