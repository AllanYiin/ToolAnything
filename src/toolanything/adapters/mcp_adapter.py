"""MCP 轉換器，將 registry 轉成 MCP server 需要的格式。"""
from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, List, Optional

from toolanything.core.registry import ToolRegistry

from .base_adapter import BaseAdapter


class MCPAdapter(BaseAdapter):
    """提供 MCP 工具列表與統一呼叫介面。"""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "ToolAnything"

    def to_schema(self) -> List[Dict[str, Any]]:
        return self.registry.to_mcp_tools()

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

    def to_capabilities(self) -> Dict[str, Any]:
        """回傳 MCP capability negotiation 所需資訊。"""

        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                    "call": True,
                    "describe": True,
                }
            },
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self._get_package_version(),
            },
            "dependencies": {
                "runtime": self._runtime_dependencies(),
                "tools": self._tool_dependencies(),
            },
        }

    def _runtime_dependencies(self) -> List[Dict[str, str]]:
        deps: List[Dict[str, str]] = [
            {"name": "python", "version": platform.python_version()},
            {"name": self.SERVER_NAME.lower(), "version": self._get_package_version()},
        ]
        return deps

    def _tool_dependencies(self) -> List[Dict[str, str]]:
        tools: List[Dict[str, str]] = []
        for name in sorted(self.registry.list_tools().keys()):
            tools.append({"name": name, "kind": "tool"})
        for name in sorted(self.registry.list_pipelines().keys()):
            tools.append({"name": name, "kind": "pipeline"})
        return tools

    def _get_package_version(self) -> str:
        try:
            return version("toolanything")
        except PackageNotFoundError:
            return "0.0.0"


def export_tools(registry: ToolRegistry) -> List[Dict[str, Any]]:
    return MCPAdapter(registry).to_schema()
