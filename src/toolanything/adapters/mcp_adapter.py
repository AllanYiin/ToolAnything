"""MCP 轉換器，將 registry 轉成 MCP server 需要的格式。"""
from __future__ import annotations

from typing import Any, Dict, List

from toolanything.core.registry import ToolRegistry


def export_tools(registry: ToolRegistry) -> List[Dict[str, Any]]:
    return registry.to_mcp_tools()
