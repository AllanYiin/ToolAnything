"""
MCP Stdio Server 實作。
提供基於標準輸入/輸出的 JSON-RPC 2.0 通訊介面，供 Claude Desktop 等客戶端使用。
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, Optional

from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.core.registry import ToolRegistry


class MCPStdioServer:
    """透過標準輸入輸出的 MCP 伺服器實作。"""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        """初始化伺服器並準備好可用的 registry 與 adapter。"""

        self.registry = registry or ToolRegistry.global_instance()
        self.adapter = MCPAdapter(self.registry)

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

    def _handle_initialize(self, request: Dict[str, Any]) -> None:
        """處理初始化請求並回傳伺服器能力描述。"""
        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": self.adapter.to_capabilities(),
        }
        self._send_message(response)

    def _handle_tools_list(self, request: Dict[str, Any]) -> None:
        """處理工具列表請求並回傳可用工具集合。"""
        tools = self.registry.to_mcp_tools()
        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": tools
            }
        }
        self._send_message(response)

    def _handle_tools_call(self, request: Dict[str, Any]) -> None:
        """根據名稱呼叫工具並回傳執行結果。"""
        params = request.get("params", {})
        name = params.get("name")
        arguments: Dict[str, Any] = params.get("arguments", {})
        
        try:
            result = self.registry.execute_tool(
                name,
                arguments=arguments,
                user_id="default",
                state_manager=None,
            )
            
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                        }
                    ]
                }
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e),
                    "data": traceback.format_exc()
                }
            }
        
        self._send_message(response)

    def run(self) -> None:
        """啟動 Stdio Server 迴圈。"""
        while True:
            request = self._read_message()
            if request is None:
                break

            method = request.get("method")
            
            if method == "initialize":
                self._handle_initialize(request)
            elif method == "notifications/initialized":
                # 客戶端確認初始化完成，無需回應
                pass
            elif method == "tools/list":
                self._handle_tools_list(request)
            elif method == "tools/call":
                self._handle_tools_call(request)
            else:
                # 未知方法或 ping
                pass

def run_stdio_server(registry: Optional[ToolRegistry] = None) -> None:
    """建立並啟動 MCP Stdio 伺服器主迴圈。"""

    server = MCPStdioServer(registry)
    server.run()
