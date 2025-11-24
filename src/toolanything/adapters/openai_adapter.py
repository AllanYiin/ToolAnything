from __future__ import annotations

from typing import Any, List

from ..core.result_serializer import ResultSerializer
from ..core.tool_registry import ToolRegistry
from ..decorators.tool_decorator import DEFAULT_REGISTRY

serializer = ResultSerializer()


def build_openai_tools(registry: ToolRegistry | None = None) -> List[dict]:
    registry = registry or DEFAULT_REGISTRY
    tools = []
    for tool in registry.list():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.path,
                    "description": tool.description,
                    "parameters": tool.input_schema or {},
                },
            }
        )
    return tools


def handle_openai_tool_calls(
    tool_calls: list[dict],
    registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or DEFAULT_REGISTRY
    results: dict[str, Any] = {}
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call.get("arguments", {})
        tool = registry.get(name)
        output = tool(**arguments)
        results[name] = serializer.to_openai(output)
    return results
