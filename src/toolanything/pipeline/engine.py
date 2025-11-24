from __future__ import annotations

from typing import Any

from ..core.tool_registry import ToolRegistry


def call_tool(name: str, /, registry: ToolRegistry | None = None, **kwargs: Any) -> Any:
    active_registry = registry or ToolRegistry.global_instance()
    tool = active_registry.get(name)
    return tool(**kwargs)
