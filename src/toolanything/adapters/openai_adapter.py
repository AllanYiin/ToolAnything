"""OpenAI Tool Calling 轉換器。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from toolanything.core.registry import ToolRegistry

from .base_adapter import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """輸出 OpenAI 工具定義並支援工具呼叫包裝。"""

    @staticmethod
    def _normalize_arguments(arguments: Any) -> Dict[str, Any]:
        """將輸入的 arguments 轉換成 dict。

        OpenAI 會以 JSON 字串傳回 arguments，此處統一處理 dict 與字串兩種型態，
        以便實際執行工具。
        """

        if arguments is None:
            return {}

        if isinstance(arguments, dict):
            return arguments

        if isinstance(arguments, str):
            return json.loads(arguments)

        raise TypeError("arguments 必須為 dict、JSON 字串或 None")

    @staticmethod
    def _serialize_content(result: Any) -> str:
        """將執行結果序列化成 tool message 內容。"""

        if isinstance(result, str):
            return result

        return json.dumps(result, ensure_ascii=False)

    def to_schema(self) -> List[Dict[str, Any]]:
        return self.registry.to_openai_tools(adapter="openai")

    def to_function_call(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """生成符合 Chat Completions tool_call 的 function 結構。"""

        normalized = self._normalize_arguments(arguments)
        return {
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(normalized, ensure_ascii=False),
            },
        }

    async def to_invocation(
        self,
        name: str,
        arguments: Optional[Any] = None,
        user_id: Optional[str] = None,
        *,
        tool_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """執行工具並回傳符合 OpenAI tool message 的格式。"""

        normalized_args = self._normalize_arguments(arguments)
        result = await self.registry.execute_tool_async(
            name,
            arguments=normalized_args,
            user_id=user_id,
            state_manager=None,
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call_id or name,
            "name": name,
            "arguments": normalized_args,
            "content": self._serialize_content(result),
            "result": result,
        }


def export_tools(registry: ToolRegistry) -> List[dict[str, Any]]:
    """輸出符合 OpenAI tool calling 的工具列表。"""
    return OpenAIAdapter(registry).to_schema()
