"""`@pipeline` decorator 實作。"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from toolanything.core.models import PipelineDefinition
from toolanything.core.registry import ToolRegistry
from toolanything.core.schema import build_parameters_schema
from toolanything.pipeline.context import PipelineContext
from toolanything.state.manager import StateManager


def pipeline(
    name: str,
    description: str,
    registry: Optional[ToolRegistry] = None,
    state_manager: Optional[StateManager] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """註冊 pipeline 函數，預設會注入 PipelineContext。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        active_registry = registry or ToolRegistry.global_instance()
        params_schema = build_parameters_schema(func)
        definition = PipelineDefinition(
            name=name,
            description=description,
            func=func,
            parameters=params_schema,
        )

        active_registry.register_pipeline(definition)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = kwargs.pop("user_id", None)
            ctx = PipelineContext(state_manager=state_manager, user_id=user_id)
            return func(ctx, *args, **kwargs)

        wrapper.metadata = definition  # type: ignore[attr-defined]
        return wrapper

    return decorator
