"""
MCP Stdio Server 實作。
提供基於標準輸入/輸出的 JSON-RPC 2.0 通訊介面，供 Claude Desktop 等客戶端使用。
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, Optional

from toolanything.core.registry import ToolRegistry


class MCPStdioServer:
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry.global_instance()

    def _read_message(self) -> Dict[str, Any] | None:
        """從 stdin 讀取一行 JSON 訊息。"""
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
        """寫入 JSON 訊息到 stdout。"""
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _handle_initialize(self, request: Dict[str, Any]) -> None:
        """處理初始化請求。"""
        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": "ToolAnything",
                    "version": "0.1.0"
                }
            }
        }
        self._send_message(response)

    def _handle_tools_list(self, request: Dict[str, Any]) -> None:
        """處理工具列表請求。"""
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
        """處理工具呼叫請求。"""
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        
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
    server = MCPStdioServer(registry)
    server.run()
