"""OpenAI Tool Calling 轉換器。"""
from __future__ import annotations

from typing import Any, List

from toolanything.core.registry import ToolRegistry


def export_tools(registry: ToolRegistry) -> List[dict[str, Any]]:
    """輸出符合 OpenAI tool calling 的工具列表。"""
    return registry.to_openai_tools()
