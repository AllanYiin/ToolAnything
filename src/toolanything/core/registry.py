"""工具與 pipeline 註冊中心。"""
from __future__ import annotations

from threading import Lock
from typing import Any, Callable, Dict

from tenacity import retry, stop_after_attempt, wait_exponential

from .models import PipelineDefinition, ToolDefinition
from ..pipeline.context import PipelineContext
from ..state.manager import StateManager


class ToolRegistry:
    _global_instance: "ToolRegistry | None" = None
    _lock = Lock()

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._pipelines: Dict[str, PipelineDefinition] = {}
        self._lookup_cache: Dict[str, Callable[..., Any]] = {}

    @classmethod
    def global_instance(cls) -> "ToolRegistry":
        """取得全域預設的惰性初始化 Registry。"""

        if cls._global_instance is None:
            with cls._lock:
                if cls._global_instance is None:
                    cls._global_instance = ToolRegistry()
        return cls._global_instance

    # 工具
    def register_tool(self, definition: ToolDefinition) -> None:
        if definition.path in self._tools:
            raise ValueError(f"工具 {definition.path} 已存在")
        self._tools[definition.path] = definition
        self._lookup_cache.clear()

    def get_tool(self, path: str) -> ToolDefinition:
        if path not in self._tools:
            raise KeyError(f"找不到工具 {path}")
        return self._tools[path]

    def list_tools(self) -> Dict[str, ToolDefinition]:
        return dict(self._tools)

    # pipeline
    def register_pipeline(self, definition: PipelineDefinition) -> None:
        if definition.name in self._pipelines:
            raise ValueError(f"Pipeline {definition.name} 已存在")
        self._pipelines[definition.name] = definition
        self._lookup_cache.clear()

    def get_pipeline(self, name: str) -> PipelineDefinition:
        if name not in self._pipelines:
            raise KeyError(f"找不到 pipeline {name}")
        return self._pipelines[name]

    def list_pipelines(self) -> Dict[str, PipelineDefinition]:
        return dict(self._pipelines)

    # Common API
    def get(self, name: str) -> Callable[..., Any]:
        if name in self._lookup_cache:
            return self._lookup_cache[name]

        if name in self._tools:
            func = self._tools[name].func
            self._lookup_cache[name] = func
            return func
        if name in self._pipelines:
            func = self._pipelines[name].func
            self._lookup_cache[name] = func
            return func
        raise KeyError(f"找不到 {name}")

    def to_openai_tools(self) -> list[dict[str, Any]]:
        entries = [definition.to_openai() for definition in self._tools.values()]
        entries += [definition.to_openai() for definition in self._pipelines.values()]
        return entries

    def to_mcp_tools(self) -> list[dict[str, Any]]:
        entries = [definition.to_mcp() for definition in self._tools.values()]
        entries += [definition.to_mcp() for definition in self._pipelines.values()]
        return entries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def execute_tool(
        self,
        name: str,
        *,
        arguments: Dict[str, Any] | None = None,
        user_id: str | None = None,
        state_manager: StateManager | None = None,
    ) -> Any:
        arguments = arguments or {}

        if name in self._pipelines:
            definition = self.get_pipeline(name)
            ctx = PipelineContext(state_manager=state_manager, user_id=user_id)
            return definition.func(ctx, **arguments)

        func = self.get(name)
        return func(**arguments)
