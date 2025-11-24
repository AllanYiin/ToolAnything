"""`@tool` decorator 實作。"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from toolanything.core.models import ToolDefinition
from toolanything.core.registry import ToolRegistry
from toolanything.core.schema import build_parameters_schema
from toolanything.utils.docstring_parser import parse_docstring


def tool(path: str, description: str, registry: Optional[ToolRegistry] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """註冊一般工具函數。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        active_registry = registry or ToolRegistry.global_instance()
        params_schema = build_parameters_schema(func)
        documentation = parse_docstring(func)
        definition = ToolDefinition(
            path=path,
            description=description,
            func=func,
            parameters=params_schema,
            documentation=documentation,
        )

        active_registry.register_tool(definition)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # 讓使用者可透過 wrapper.metadata 取得 schema
        wrapper.metadata = definition  # type: ignore[attr-defined]
        return wrapper

    return decorator
