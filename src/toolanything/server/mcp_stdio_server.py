"""
MCP Stdio Server 實作。
提供基於標準輸入/輸出的 JSON-RPC 2.0 通訊介面，供 Claude Desktop 等客戶端使用。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

from ..core.registry import ToolRegistry
from ..core.result_serializer import ResultSerializer
from ..core.security_manager import SecurityManager
from ..protocol.mcp_jsonrpc import MCPProtocolCoreImpl, MCPRequestContext
from .mcp_runtime import build_protocol_dependencies


class MCPStdioServer:
    """透過標準輸入輸出的 MCP 伺服器實作。"""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        """初始化伺服器並準備好可用的 registry 與 adapter。"""

        self.registry = registry or ToolRegistry.global_instance()
        self.adapter, self.result_serializer, self.security_manager, self._deps = (
            build_protocol_dependencies(self.registry)
        )
        self.result_serializer: ResultSerializer
        self.security_manager: SecurityManager
        self._protocol_core = MCPProtocolCoreImpl()
        self._default_user_id = os.getenv("TOOLANYTHING_USER_ID", "default")

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

            context = MCPRequestContext(user_id=self._default_user_id, transport="stdio")
            response = self._protocol_core.handle(request, context=context, deps=self._deps)
            if response is not None:
                self._send_message(response)

def run_stdio_server(registry: Optional[ToolRegistry] = None) -> None:
    """建立並啟動 MCP Stdio 伺服器主迴圈。"""

    server = MCPStdioServer(registry)
    server.run()
