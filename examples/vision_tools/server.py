from __future__ import annotations

import argparse

from toolanything import ToolRegistry
from toolanything.server.mcp_streamable_http import run_server
from toolanything.utils.logger import logger

# 載入工具，讓 decorator 註冊到全域 registry
from .yolo_person_tool import detect_person  # noqa: F401

registry = ToolRegistry.global_instance()


def start_server(port: int = 9093, host: str = "127.0.0.1") -> None:
    """Start an MCP HTTP server exposing the YOLOv8 person detection tool."""

    run_server(port=port, host=host, registry=registry)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="啟動 YOLOv8 person MCP server")
    parser.add_argument("--port", type=int, default=9093, help="監聽 port，預設 9093")
    parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    print("[vision_tools] 已註冊工具：")
    for tool_info in registry.to_mcp_tools():
        print(f" - {tool_info['name']}: {tool_info['description']}")

    try:
        start_server(port=args.port, host=args.host)
    except Exception:
        logger.exception("YOLOv8 MCP 伺服器啟動失敗")
        print("[vision_tools] 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
