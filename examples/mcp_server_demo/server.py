"""最小可執行的 MCP Server 範例（啟動 HTTP 服務並可搭配 dummy client 驗證）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from toolanything import ToolRegistry, tool
from toolanything.server.mcp_tool_server import run_server

registry = ToolRegistry()


@tool(name="echo.text", description="回聲輸出", registry=registry)
def echo(text: str) -> dict[str, Any]:
    """將輸入文字以回聲方式回傳。"""

    return {"echo": text}


def start_server(port: int, host: str = "0.0.0.0") -> None:
    """啟動綁定本範例工具的 MCP HTTP Server。"""

    run_server(port=port, host=host, registry=registry)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="啟動 mcp_server_demo")
    parser.add_argument("--port", type=int, default=9090, help="監聽 port，預設 9090")
    parser.add_argument("--host", default="0.0.0.0", help="監聽 host，預設 0.0.0.0")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    print("[mcp_server_demo] 範例工具列表：")
    for tool_info in registry.to_mcp_tools():
        print(f" - {tool_info['name']}: {tool_info['description']}")

    print("[mcp_server_demo] 若要在另一個終端機執行 dummy client，請保持此伺服器運行。")
    start_server(port=args.port, host=args.host)


if __name__ == "__main__":
    main()
