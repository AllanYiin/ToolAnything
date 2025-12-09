"""`@tool` decorator 實作。"""
from __future__ import annotations

from dataclasses import replace
from functools import wraps
from typing import Any, Callable, Optional

from toolanything.core.models import ToolSpec
from toolanything.core.registry import ToolRegistry


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    adapters: list[str] | None = None,
    tags: list[str] | None = None,
    strict: bool = True,
    metadata: dict[str, Any] | None = None,
    registry: Optional[ToolRegistry] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]] | Callable[..., Any]:
    """註冊工具函數並產生統一的 :class:`ToolSpec` 描述。

    若未提供 description，會優先使用 docstring 第一段。strict 為 True 且仍無
    描述時會拋出錯誤。
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        active_registry = registry or ToolRegistry.global_instance()
        spec = ToolSpec.from_function(
            fn,
            name=name,
            description=description,
            adapters=adapters,
            tags=tags,
            strict=strict,
            metadata=metadata,
        )

        # 為了讓 adapter 取得預設 adapter 設定，若 decorator 未指定 adapters 則
        # 保留 None，讓外部 manager/registry 可套用全域預設。
        if adapters is None and hasattr(active_registry, "default_adapters"):
            spec = replace(spec, adapters=getattr(active_registry, "default_adapters"))

        active_registry.register(spec)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        wrapper.tool_spec = spec  # type: ignore[attr-defined]
        return wrapper

    if func is not None and callable(func):
        return decorator(func)

    return decorator
