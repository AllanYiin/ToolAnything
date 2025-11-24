from __future__ import annotations

from typing import Any, List

from ..core.result_serializer import ResultSerializer
from ..core.tool_registry import ToolRegistry
from ..decorators.tool_decorator import DEFAULT_REGISTRY

serializer = ResultSerializer()


class CallToolResult(dict):
    """Lightweight result object for MCP calls."""

    def __init__(self, content: Any, content_type: str = "application/json"):
        super().__init__({"content": content, "contentType": content_type})


class MCPToolServer:
    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or DEFAULT_REGISTRY

    async def list_tools(self) -> List[dict]:
        return [
            {
                "name": tool.path,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self.registry.list()
        ]

    async def call_tool(self, name: str, arguments: dict) -> CallToolResult:
        tool = self.registry.get(name)
        result = tool(**arguments)
        serialized = serializer.to_mcp(result)
        return CallToolResult(serialized["content"], serialized["contentType"])
