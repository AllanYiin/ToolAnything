"""
ToolAnything MCP Server Demo
這個範例展示如何將一個簡單的 Python 函數包裝成 MCP Tool，並啟動 Server。
"""
import sys
import os

# 確保可以 import 到 src 下的套件 (如果是在開發環境中執行)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from toolanything.decorators import tool
from toolanything.server.mcp_tool_server import run_server

@tool(path="calculator_add", description="計算兩個數字的總和")
def add(a: int, b: int) -> int:
    """
    將兩個整數相加。
    
    Args:
        a: 第一個數字
        b: 第二個數字
    """
    return a + b

@tool(path="string_reverse", description="反轉字串")
def reverse_string(text: str) -> str:
    """
    將輸入的字串反轉。
    
    Args:
        text: 要反轉的文字
    """
    return text[::-1]

if __name__ == "__main__":
    # 啟動 MCP Server，預設 Port 為 9090
    print("正在啟動 MCP Server...")
    print("請確保您已經使用 `python -m toolanything.cli install-claude` 或手動設定 Claude Desktop")
    run_server(port=9090)
