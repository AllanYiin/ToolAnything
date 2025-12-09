"""MCP 轉換器，將 registry 轉成 MCP server 需要的格式。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from toolanything.core.registry import ToolRegistry

from .base_adapter import BaseAdapter


class MCPAdapter(BaseAdapter):
    """提供 MCP 工具列表與統一呼叫介面。"""

    def to_schema(self) -> List[Dict[str, Any]]:
        return self.registry.to_mcp_tools(adapter="mcp")

    def to_invocation(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self.registry.execute_tool(
            name,
            arguments=arguments or {},
            user_id=user_id,
            state_manager=None,
        )
        return {
            "name": name,
            "arguments": arguments or {},
            "result": result,
        }


def export_tools(registry: ToolRegistry) -> List[Dict[str, Any]]:
    return MCPAdapter(registry).to_schema()
