from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from ..core.schema_engine import build_input_schema, build_output_schema
from ..core.tool_definition import ToolDefinition
from ..core.tool_registry import ToolRegistry


DEFAULT_REGISTRY = ToolRegistry()


def tool(
    *,
    name: str | None = None,
    path: str | None = None,
    description: str | None = None,
    group: str | None = None,
    registry: ToolRegistry | None = None,
):
    registry = registry or DEFAULT_REGISTRY

    def decorator(fn: Callable[..., Any]):
        args, input_schema = build_input_schema(fn)
        output_schema = build_output_schema(fn.__annotations__.get("return"))
        definition = ToolDefinition(
            name=name or fn.__name__,
            path=path or name or fn.__name__,
            description=description or fn.__doc__,
            args=args,
            return_type=fn.__annotations__.get("return"),
            func=fn,
            input_schema=input_schema,
            output_schema=output_schema,
            group=group,
            annotations={},
            extra={},
        )
        registry.register(definition)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            return fn(*args, **kwargs)

        wrapper.tool_definition = definition  # type: ignore[attr-defined]
        return wrapper

    return decorator
