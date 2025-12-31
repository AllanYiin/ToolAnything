"""Doctor 專用的 MCP stdio server 啟動器。"""
from __future__ import annotations

import argparse
import sys

from toolanything.core.builtin_tools import register_ping_tool
from toolanything.core.registry import ToolRegistry
from toolanything.runtime.serve import load_tool_module
from toolanything.server.mcp_stdio_server import run_stdio_server
from toolanything.utils.logger import configure_logging, logger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toolanything-doctor-server")
    parser.add_argument(
        "--tools",
        required=True,
        help="工具模組路徑（例如 examples.quickstart.tools）",
    )
    return parser


def main() -> None:
    configure_logging()
    parser = _build_parser()
    args = parser.parse_args()

    try:
        load_tool_module(args.tools)
        registry = ToolRegistry.global_instance()
        register_ping_tool(registry)
        run_stdio_server(registry)
    except Exception:
        logger.exception("Doctor stdio server 啟動失敗")
        print("[ToolAnything] Doctor stdio server 啟動失敗，請查看 logs/toolanything.log")
        sys.exit(1)


if __name__ == "__main__":
    main()
