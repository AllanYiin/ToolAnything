"""
ToolAnything MCP Streamable HTTP Demo
這個範例展示如何將簡單的 Python 函數註冊成 tool，並用新版 Streamable HTTP transport 啟動。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from toolanything.decorators import tool
from toolanything.server.mcp_streamable_http import run_server


@tool(name="calculator_add", description="計算兩個數字的總和")
def add(a: int, b: int) -> int:
    return a + b


@tool(name="string_reverse", description="反轉字串")
def reverse_string(text: str) -> str:
    return text[::-1]


if __name__ == "__main__":
    print("正在啟動 MCP Streamable HTTP server...")
    print("主端點：http://127.0.0.1:9092/mcp")
    print("如果你想看由淺入深的 raw transport 範例，請改跑 examples/streamable_http/*.py")
    run_server(port=9092)
