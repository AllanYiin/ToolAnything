"""OpenAI Tool Calling 轉換器。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from toolanything.core.registry import ToolRegistry

from .base_adapter import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """輸出 OpenAI 工具定義並支援工具呼叫包裝。"""

    def to_schema(self) -> List[Dict[str, Any]]:
        return self.registry.to_openai_tools(adapter="openai")

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
            "type": "function",
            "name": name,
            "arguments": arguments or {},
            "result": result,
        }


def export_tools(registry: ToolRegistry) -> List[dict[str, Any]]:
    """輸出符合 OpenAI tool calling 的工具列表。"""
    return OpenAIAdapter(registry).to_schema()
