from __future__ import annotations

from typing import Any

from ..core.tool_registry import ToolRegistry
from ..decorators.tool_decorator import DEFAULT_REGISTRY


def call_tool(name: str, /, registry: ToolRegistry | None = None, **kwargs: Any) -> Any:
    registry = registry or DEFAULT_REGISTRY
    tool = registry.get(name)
    return tool(**kwargs)
