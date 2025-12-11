"""工具與 pipeline 註冊中心。"""
from __future__ import annotations

import asyncio
import inspect
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from .failure_log import FailureLogManager
from .models import PipelineDefinition, ToolSpec
from ..pipeline.context import PipelineContext
from ..state.manager import StateManager


class ToolRegistry:
    _global_instance: "ToolRegistry | None" = None
    _lock = Lock()

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}
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
    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具 {spec.name} 已存在")
        self._tools[spec.name] = spec
        self._lookup_cache.clear()

    # 舊介面的相容別名
    def register_tool(self, definition: ToolSpec) -> None:
        self.register(definition)

    def unregister(self, name: str) -> None:
        if name not in self._tools:
            raise KeyError(f"找不到工具 {name}")
        del self._tools[name]
        self._lookup_cache.clear()

    def get_tool(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"找不到工具 {name}")
        return self._tools[name]

    def list(self, *, tags: Optional[List[str]] = None) -> List[ToolSpec]:
        specs = list(self._tools.values())
        if not tags:
            return specs

        tag_set = set(tags)
        return [spec for spec in specs if tag_set.issubset(set(spec.tags))]

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

    def to_openai_tools(self, *, adapter: str | None = None) -> list[dict[str, Any]]:
        entries = [
            definition.to_openai()
            for definition in self._tools.values()
            if adapter is None
            or definition.adapters is None
            or adapter in definition.adapters
        ]
        entries += [definition.to_openai() for definition in self._pipelines.values()]
        return entries

    def to_mcp_tools(self, *, adapter: str | None = None) -> list[dict[str, Any]]:
        entries = [
            definition.to_mcp()
            for definition in self._tools.values()
            if adapter is None
            or definition.adapters is None
            or adapter in definition.adapters
        ]
        entries += [definition.to_mcp() for definition in self._pipelines.values()]
        return entries

    def _build_context(
        self, *, user_id: str | None, state_manager: StateManager | None
    ) -> PipelineContext:
        return PipelineContext(state_manager=state_manager, user_id=user_id)

    async def _execute_callable(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """在 async 環境下執行函數，必要時轉為 thread 以避免阻塞。"""

        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)

        result = await asyncio.to_thread(func, *args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def execute_tool_async(
        self,
        name: str,
        *,
        arguments: Dict[str, Any] | None = None,
        user_id: str | None = None,
        state_manager: StateManager | None = None,
        failure_log: FailureLogManager | None = None,
    ) -> Any:
        arguments = arguments or {}

        if name in self._pipelines:
            definition = self.get_pipeline(name)
            ctx = self._build_context(user_id=user_id, state_manager=state_manager)
            try:
                return await self._execute_callable(definition.func, ctx, **arguments)
            except Exception:
                if failure_log:
                    failure_log.record_failure(name)
                raise

        func = self.get(name)
        try:
            return await self._execute_callable(func, **arguments)
        except Exception:
            if failure_log:
                failure_log.record_failure(name)
            raise

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
        failure_log: FailureLogManager | None = None,
    ) -> Any:
        """同步介面：在未啟動事件迴圈時執行，否則要求使用 async 版本。"""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.execute_tool_async(
                    name,
                    arguments=arguments,
                    user_id=user_id,
                    state_manager=state_manager,
                    failure_log=failure_log,
                )
            )

        raise RuntimeError(
            "事件迴圈運行時請改用 execute_tool_async 以避免阻塞。"
        )
