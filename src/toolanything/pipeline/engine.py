from __future__ import annotations

from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.tool_registry import ToolRegistry


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
)
def execute_tool(name: str, /, registry: ToolRegistry | None = None, **kwargs: Any) -> Any:
    active_registry = registry or ToolRegistry.global_instance()
    tool = active_registry.get(name)
    return tool(**kwargs)


def call_tool(name: str, /, registry: ToolRegistry | None = None, **kwargs: Any) -> Any:
    return execute_tool(name, registry=registry, **kwargs)
