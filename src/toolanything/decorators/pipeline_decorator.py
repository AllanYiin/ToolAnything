from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from ..core.tool_definition import ToolDefinition
from ..core.tool_registry import ToolRegistry
from ..core.schema_engine import build_input_schema, build_output_schema
from ..pipeline.engine import call_tool
from ..state.context import StateContext


def pipeline(
    *,
    name: str,
    description: str | None = None,
    registry: ToolRegistry | None = None,
):
    def decorator(fn: Callable[..., Any]):
        active_registry = registry or ToolRegistry.global_instance()
        args, input_schema = build_input_schema(fn)
        output_schema = build_output_schema(fn.__annotations__.get("return"))
        definition = ToolDefinition(
            name=name.split(".")[-1],
            path=name,
            description=description or fn.__doc__,
            args=args,
            return_type=fn.__annotations__.get("return"),
            func=fn,
            input_schema=input_schema,
            output_schema=output_schema,
            annotations={"type": "pipeline"},
            extra={},
        )
        active_registry.register(definition)

        @wraps(fn)
        def wrapper(ctx: StateContext, *args: Any, **kwargs: Any):
            return fn(ctx, *args, **kwargs)

        wrapper.tool_definition = definition  # type: ignore[attr-defined]
        wrapper.call_tool = lambda tool_name, **kwargs: call_tool(tool_name, registry=active_registry, **kwargs)  # type: ignore[attr-defined]
        return wrapper

    return decorator
