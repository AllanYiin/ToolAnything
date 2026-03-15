"""`@tool` decorator 實作。"""
from __future__ import annotations

import inspect
from dataclasses import replace
from functools import update_wrapper
from typing import Any, Callable, Optional

from ..core.models import ToolSpec
from ..core.registry import ToolRegistry

_CLASS_HOOK_PREFIX = "__toolanything_pending_tool__"


def _unwrap_callable_target(target: Any) -> Any:
    return getattr(target, "__func__", target)


def _is_class_body_frame(frame: inspect.FrameInfo | Any | None) -> bool:
    if frame is None:
        return False
    local_vars = getattr(frame, "f_locals", {})
    return "__module__" in local_vars and "__qualname__" in local_vars


class _ToolRegistrationHook:
    """Bridge descriptor for `@classmethod` / `@staticmethod` stacked over `@tool`."""

    def __init__(self, wrapped: "_ToolDecoratorWrapper", method_name: str) -> None:
        self._wrapped = wrapped
        self._method_name = method_name

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._wrapped.register_for_owner(owner, self._method_name)
        try:
            delattr(owner, name)
        except AttributeError:
            pass


class _ToolDecoratorWrapper:
    """Callable/descriptor wrapper that defers registration until owner is known."""

    def __init__(
        self,
        target: Any,
        *,
        name: str | None,
        description: str | None,
        adapters: list[str] | None,
        tags: list[str] | None,
        strict: bool,
        metadata: dict[str, Any] | None,
        registry: ToolRegistry | None,
    ) -> None:
        self._target = target
        self._name = name
        self._description = description
        self._adapters = adapters
        self._tags = tags
        self._strict = strict
        self._metadata = metadata
        self._registry = registry
        self._registered = False
        self._registered_owner: type[Any] | None = None
        self.tool_spec: ToolSpec | None = None

        update_wrapper(self, _unwrap_callable_target(target))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        callable_target = self._resolve_runtime_callable()
        return callable_target(*args, **kwargs)

    def __get__(self, instance: Any, owner: type[Any] | None = None) -> Any:
        descriptor_get = getattr(self._target, "__get__", None)
        if callable(descriptor_get):
            return descriptor_get(instance, owner)
        return self

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self.register_for_owner(owner, name)

    def register_immediately(self) -> None:
        if self._registered:
            return
        spec = self._build_spec(self._resolve_runtime_callable())
        self._active_registry().register(spec)
        self.tool_spec = spec
        self._registered = True

    def register_for_owner(self, owner: type[Any], attribute_name: str) -> None:
        if self._registered:
            return
        spec = self._build_spec(getattr(owner, attribute_name))
        self._active_registry().register(spec)
        self.tool_spec = spec
        self._registered = True
        self._registered_owner = owner

    def _active_registry(self) -> ToolRegistry:
        return self._registry or ToolRegistry.global_instance()

    def _resolve_runtime_callable(self) -> Callable[..., Any]:
        if callable(self._target):
            return self._target
        if self._registered_owner is not None:
            return self.__get__(None, self._registered_owner)
        raise TypeError(f"{self._target!r} is not a callable object")

    def _build_spec(self, func: Callable[..., Any]) -> ToolSpec:
        spec = ToolSpec.from_function(
            func,
            name=self._name,
            description=self._description,
            adapters=self._adapters,
            tags=self._tags,
            strict=self._strict,
            metadata=self._metadata,
        )

        active_registry = self._active_registry()
        if self._adapters is None and hasattr(active_registry, "default_adapters"):
            spec = replace(spec, adapters=getattr(active_registry, "default_adapters"))
        return spec


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
        wrapped = _ToolDecoratorWrapper(
            fn,
            name=name,
            description=description,
            adapters=adapters,
            tags=tags,
            strict=strict,
            metadata=metadata,
            registry=registry,
        )

        caller_frame = inspect.currentframe().f_back
        if _is_class_body_frame(caller_frame):
            hook_name = f"{_CLASS_HOOK_PREFIX}{wrapped.__name__}"
            caller_frame.f_locals[hook_name] = _ToolRegistrationHook(wrapped, wrapped.__name__)
        else:
            wrapped.register_immediately()

        return wrapped

    if func is not None:
        return decorator(func)

    return decorator
