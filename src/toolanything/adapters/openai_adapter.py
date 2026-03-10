"""OpenAI Tool Calling 轉換器。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..core.registry import ToolRegistry
from ..exceptions import ToolError
from ..utils.openai_tool_names import build_openai_name_mappings

from .base_adapter import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """輸出 OpenAI 工具定義並支援工具呼叫包裝。"""

    def _build_name_mappings(self) -> tuple[dict[str, str], dict[str, str]]:
        tool_names = [tool["name"] for tool in self.registry.to_mcp_tools(adapter="openai")]
        return build_openai_name_mappings(tool_names)

    def to_openai_name(self, name: str) -> str:
        original_to_openai, openai_to_original = self._build_name_mappings()
        if name in original_to_openai:
            return original_to_openai[name]
        if name in openai_to_original:
            return name
        return build_openai_name_mappings([name])[0][name]

    def from_openai_name(self, name: str) -> str:
        _, openai_to_original = self._build_name_mappings()
        return openai_to_original.get(name, name)

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
    def _serialize_content(result: Dict[str, Any]) -> str:
        """將標準化後的結果轉為 tool message 字串。"""

        if result.get("type") == "text":
            return str(result.get("content", ""))

        return json.dumps(result.get("content"), ensure_ascii=False)

    def to_schema(self) -> List[Dict[str, Any]]:
        original_to_openai, _ = self._build_name_mappings()
        tools = self.registry.to_openai_tools(adapter="openai")
        normalized_tools: list[dict[str, Any]] = []
        for tool in tools:
            function = dict(tool["function"])
            function["name"] = original_to_openai.get(function["name"], function["name"])
            normalized_tool = dict(tool)
            normalized_tool["function"] = function
            normalized_tools.append(normalized_tool)
        return normalized_tools

    def to_function_call(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        tool_call_id: str | None = None,
    ) -> Dict[str, Any]:
        """生成符合 Chat Completions tool_call 的 function 結構。"""

        normalized = self._normalize_arguments(arguments)
        resolved_name = self.to_openai_name(name)
        payload = {
            "type": "function",
            "function": {
                "name": resolved_name,
                "arguments": json.dumps(normalized, ensure_ascii=False),
            },
        }
        if tool_call_id:
            payload["id"] = tool_call_id
        return payload

    async def to_invocation(
        self,
        name: str,
        arguments: Optional[Any] = None,
        user_id: Optional[str] = None,
        *,
        tool_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """執行工具並回傳符合 OpenAI tool message 的格式。"""

        original_name = self.from_openai_name(name)
        normalized_args = self._normalize_arguments(arguments)
        audit_log = self.security_manager.audit_call(original_name, normalized_args, user_id)
        masked_args = self.security_manager.mask_keys_in_log(normalized_args)

        try:
            result = await self.registry.invoke_tool_async(
                original_name,
                arguments=normalized_args,
                user_id=user_id,
                state_manager=None,
                failure_log=self.failure_log,
            )
            serialized_result = self.result_serializer.to_openai(result)
            content = self._serialize_content(serialized_result)
            return {
                "role": "tool",
                "tool_call_id": tool_call_id or original_name,
                "name": original_name,
                "arguments": masked_args,
                "content": content,
                "result": serialized_result,
                "raw_result": result,
                "audit": audit_log,
            }
        except ToolError as exc:
            error_payload = exc.to_dict()
            return {
                "role": "tool",
                "tool_call_id": tool_call_id or original_name,
                "name": original_name,
                "arguments": masked_args,
                "content": json.dumps(error_payload, ensure_ascii=False),
                "error": error_payload,
                "audit": audit_log,
            }
        except Exception:
            error_payload = {"type": "internal_error", "message": "工具執行時發生未預期錯誤"}
            return {
                "role": "tool",
                "tool_call_id": tool_call_id or original_name,
                "name": original_name,
                "arguments": masked_args,
                "content": json.dumps(error_payload, ensure_ascii=False),
                "error": error_payload,
                "audit": audit_log,
            }


def export_tools(registry: ToolRegistry) -> List[dict[str, Any]]:
    """輸出符合 OpenAI tool calling 的工具列表。"""
    return OpenAIAdapter(registry).to_schema()
