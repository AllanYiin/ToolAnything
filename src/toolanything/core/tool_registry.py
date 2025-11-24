from __future__ import annotations

from threading import Lock
from typing import Dict, List

from .tool_definition import ToolDefinition


class ToolRegistry:
    _global_instance: "ToolRegistry | None" = None
    _lock = Lock()

    def __init__(self, namespace: str | None = None):
        self.namespace = namespace
        self._tools: Dict[str, ToolDefinition] = {}

    @classmethod
    def global_instance(cls) -> "ToolRegistry":
        """取得全域預設的惰性初始化 Registry。"""

        if cls._global_instance is None:
            with cls._lock:
                if cls._global_instance is None:
                    cls._global_instance = ToolRegistry(namespace="default")
        return cls._global_instance

    def register(self, tool: ToolDefinition) -> None:
        key = tool.path or tool.name
        if key in self._tools:
            raise ValueError(f"Tool '{key}' already registered")
        self._tools[key] = tool

    def get(self, name_or_path: str) -> ToolDefinition:
        if name_or_path in self._tools:
            return self._tools[name_or_path]
        raise KeyError(f"Tool '{name_or_path}' not found")

    def list(self, recursive: bool = False) -> List[ToolDefinition]:
        if recursive or not self.namespace:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.path.startswith(f"{self.namespace}.")]

    def merge(self, other_registry: "ToolRegistry") -> None:
        for path, tool in other_registry._tools.items():
            if path in self._tools:
                raise ValueError(f"Conflict merging tool '{path}'")
            self._tools[path] = tool
