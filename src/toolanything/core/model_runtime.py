"""Model runtime helpers."""
from __future__ import annotations

from typing import Any, Callable


class ModelHookRegistry:
    """可註冊 pre/post processor hooks。"""

    def __init__(self) -> None:
        self._hooks: dict[str, Callable[[Any], Any]] = {}

    def register(self, ref: str, hook: Callable[[Any], Any]) -> None:
        self._hooks[ref] = hook

    def resolve(self, ref: str | None) -> Callable[[Any], Any] | None:
        if not ref:
            return None
        return self._hooks.get(ref)


class ModelSessionCache:
    """模型/Session lazy load cache。"""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], Any] = {}

    def get_or_load(self, key: tuple[str, str, str], loader: Callable[[], Any]) -> Any:
        if key not in self._entries:
            self._entries[key] = loader()
        return self._entries[key]


__all__ = ["ModelHookRegistry", "ModelSessionCache"]
