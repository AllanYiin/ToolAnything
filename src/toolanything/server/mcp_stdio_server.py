"""
MCP Stdio Server 實作。
提供基於標準輸入/輸出的 JSON-RPC 2.0 通訊介面，供 Claude Desktop 等客戶端使用。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.core.registry import ToolRegistry
from toolanything.core.result_serializer import ResultSerializer
from toolanything.core.security_manager import SecurityManager
from toolanything.protocol.mcp_jsonrpc import MCPProtocolCoreImpl, MCPRequestContext


class _CapabilitiesProvider:
    def __init__(self, adapter: MCPAdapter):
        self._adapter = adapter

    def get_capabilities(self) -> Dict[str, Any]:
        return self._adapter.to_capabilities()


class _ToolSchemaProvider:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def list_tools(self) -> list[Dict[str, Any]]:
        return self._registry.to_mcp_tools()


class _ToolInvoker:
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
class _ProtocolDependencies:
    capabilities: _CapabilitiesProvider
    tools: _ToolSchemaProvider
    invoker: _ToolInvoker


class MCPStdioServer:
    """透過標準輸入輸出的 MCP 伺服器實作。"""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        """初始化伺服器並準備好可用的 registry 與 adapter。"""

        self.registry = registry or ToolRegistry.global_instance()
        self.adapter = MCPAdapter(self.registry)
        self.result_serializer: ResultSerializer = self.adapter.result_serializer
        self.security_manager: SecurityManager = self.adapter.security_manager
        self._protocol_core = MCPProtocolCoreImpl()
        self._deps = _ProtocolDependencies(
            capabilities=_CapabilitiesProvider(self.adapter),
            tools=_ToolSchemaProvider(self.registry),
            invoker=_ToolInvoker(self.registry, self.result_serializer, self.security_manager),
        )

    def _read_message(self) -> Dict[str, Any] | None:
        """從 stdin 讀取一行 JSON 訊息並轉為字典。"""

        try:
            line = sys.stdin.readline()
            if not line:
                return None
            return json.loads(line)
        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def _send_message(self, message: Dict[str, Any]) -> None:
        """將字典轉為 JSON 字串後寫入 stdout。"""
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def run(self) -> None:
        """啟動 Stdio Server 迴圈。"""
        while True:
            request = self._read_message()
            if request is None:
                break

            context = MCPRequestContext(user_id="default", transport="stdio")
            response = self._protocol_core.handle(request, context=context, deps=self._deps)
            if response is not None:
                self._send_message(response)

def run_stdio_server(registry: Optional[ToolRegistry] = None) -> None:
    """建立並啟動 MCP Stdio 伺服器主迴圈。"""

    server = MCPStdioServer(registry)
    server.run()
