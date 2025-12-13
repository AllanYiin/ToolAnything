"""MCP 轉換器，將 registry 轉成 MCP server 需要的格式。"""
from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, List, Optional

from toolanything.core.registry import ToolRegistry
from toolanything.exceptions import ToolError

from .base_adapter import BaseAdapter


class MCPAdapter(BaseAdapter):
    """提供 MCP 工具列表與統一呼叫介面。"""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "ToolAnything"

    def to_schema(self) -> List[Dict[str, Any]]:
        return self.registry.to_mcp_tools(adapter="mcp")

    async def to_invocation(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_args = arguments or {}
        audit_log = self.security_manager.audit_call(name, normalized_args, user_id)
        masked_args = self.security_manager.mask_keys_in_log(normalized_args)

        try:
            result = await self.registry.execute_tool_async(
                name,
                arguments=normalized_args,
                user_id=user_id,
                state_manager=None,
                failure_log=self.failure_log,
            )
            serialized = self.result_serializer.to_mcp(result)
            return {
                "name": name,
                "arguments": masked_args,
                "result": serialized,
                "raw_result": result,
                "audit": audit_log,
            }
        except ToolError as exc:
            return {
                "name": name,
                "arguments": masked_args,
                "error": exc.to_dict(),
                "audit": audit_log,
            }
        except Exception:
            return {
                "name": name,
                "arguments": masked_args,
                "error": {"type": "internal_error", "message": "工具執行時發生未預期錯誤"},
                "audit": audit_log,
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

        # 向後相容：部分 Registry 使用 list_tools/list_pipelines，
        # 另一版本使用 list()/to_mcp_tools() 介面。
        list_tools = getattr(self.registry, "list_tools", None)
        list_pipelines = getattr(self.registry, "list_pipelines", None)

        if callable(list_tools):
            tool_entries = self.registry.list_tools()
            if isinstance(tool_entries, dict):
                tool_names = tool_entries.keys()
            else:
                tool_names = [
                    getattr(item, "path", getattr(item, "name", ""))
                    for item in tool_entries
                ]
            for name in sorted(tool_names):
                tools.append({"name": name, "kind": "tool"})
        else:
            for entry in self.registry.to_mcp_tools():
                name = entry.get("name")
                if name:
                    tools.append({"name": name, "kind": "tool"})

        if callable(list_pipelines):
            pipeline_entries = self.registry.list_pipelines()
            pipeline_names = (
                pipeline_entries.keys()
                if isinstance(pipeline_entries, dict)
                else [
                    getattr(item, "name", getattr(item, "path", ""))
                    for item in pipeline_entries
                ]
            )
            for name in sorted(pipeline_names):
                tools.append({"name": name, "kind": "pipeline"})
        elif hasattr(self.registry, "_pipelines"):
            for name in sorted(getattr(self.registry, "_pipelines").keys()):
                tools.append({"name": name, "kind": "pipeline"})

        return tools

    def _get_package_version(self) -> str:
        try:
            return version("toolanything")
        except PackageNotFoundError:
            return "0.0.0"


def export_tools(registry: ToolRegistry) -> List[Dict[str, Any]]:
    return MCPAdapter(registry).to_schema()
