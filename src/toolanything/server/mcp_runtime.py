"""Shared MCP protocol/runtime wiring for multiple transports."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from ..adapters.mcp_adapter import MCPAdapter
from ..core.registry import ToolRegistry
from ..core.result_serializer import ResultSerializer
from ..core.security_manager import SecurityManager
from ..protocol.mcp_jsonrpc import MCPRequestContext


class CapabilitiesProvider:
    def __init__(self, adapter: MCPAdapter):
        self._adapter = adapter

    def get_capabilities(self) -> Dict[str, Any]:
        return self._adapter.to_capabilities()


class ToolSchemaProvider:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def list_tools(self) -> list[Dict[str, Any]]:
        return self._registry.to_mcp_tools()


class ToolInvoker:
    def __init__(
        self,
        registry: ToolRegistry,
        serializer: ResultSerializer,
        security_manager: SecurityManager,
    ):
        self._registry = registry
        self._serializer = serializer
        self._security_manager = security_manager

    def _audit(self, name: str, arguments: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        return self._security_manager.audit_call(name or "", arguments, user_id)

    def _mask(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._security_manager.mask_keys_in_log(arguments)

    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        context: MCPRequestContext,
    ) -> Dict[str, Any]:
        user_id = context.user_id or "default"
        masked_args = self._mask(arguments)
        audit_log = self._audit(name or "", arguments, user_id)

        result = self._registry.execute_tool(
            name,
            arguments=arguments,
            user_id=user_id,
            state_manager=None,
        )
        serialized = self._serializer.to_mcp(result)
        text_content = (
            json.dumps(serialized["content"], ensure_ascii=False)
            if serialized.get("contentType") == "application/json"
            else str(serialized.get("content"))
        )
        return {
            "content": [{"type": "text", "text": text_content}],
            "meta": {"contentType": serialized.get("contentType")},
            "arguments": masked_args,
            "audit": audit_log,
            "raw_result": result,
        }


@dataclass(frozen=True)
class ProtocolDependencies:
    capabilities: CapabilitiesProvider
    tools: ToolSchemaProvider
    invoker: ToolInvoker


def build_protocol_dependencies(
    registry: ToolRegistry,
    *,
    serializer: ResultSerializer | None = None,
    security_manager: SecurityManager | None = None,
) -> tuple[MCPAdapter, ResultSerializer, SecurityManager, ProtocolDependencies]:
    adapter = MCPAdapter(registry)
    active_serializer = serializer or adapter.result_serializer
    active_security_manager = security_manager or adapter.security_manager
    deps = ProtocolDependencies(
        capabilities=CapabilitiesProvider(adapter),
        tools=ToolSchemaProvider(registry),
        invoker=ToolInvoker(registry, active_serializer, active_security_manager),
    )
    return adapter, active_serializer, active_security_manager, deps


__all__ = [
    "CapabilitiesProvider",
    "ToolSchemaProvider",
    "ToolInvoker",
    "ProtocolDependencies",
    "build_protocol_dependencies",
]
