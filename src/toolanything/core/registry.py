"""工具與 pipeline 註冊中心。"""
from __future__ import annotations

import asyncio
import inspect
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from .failure_log import FailureLogManager
from .models import PipelineDefinition, ToolSpec
from ..pipeline.context import PipelineContext, is_context_parameter
from ..state.manager import StateManager


class ToolRegistry:
    _global_instance: "ToolRegistry | None" = None
    _lock = Lock()

    def __init__(
        self,
        *,
        tool_prefix: str = "tool:",
        pipeline_prefix: str = "pipeline:",
        enable_type_prefix: bool = True,
    ) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        self._pipelines: Dict[str, PipelineDefinition] = {}
        self._lookup_cache: Dict[Tuple[str | None, str], Callable[..., Any]] = {}

        self.tool_prefix = tool_prefix
        self.pipeline_prefix = pipeline_prefix
        self.enable_type_prefix = enable_type_prefix

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
        kind, normalized_name = self._parse_lookup_name(spec.name)
        if kind == "pipeline":
            raise ValueError(
                f"名稱 {spec.name} 使用了 pipeline 前綴，請改用 register_pipeline 註冊"
            )

        self._assert_not_duplicated(normalized_name, current_kind="tool")
        self._tools[normalized_name] = spec
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
        target, normalized_name = self._normalize_lookup_target(name)
        if target not in (None, "tool") or normalized_name not in self._tools:
            raise KeyError(f"找不到工具 {name}")
        return self._tools[normalized_name]

    def list(self, *, tags: Optional[List[str]] = None) -> List[ToolSpec]:
        specs = list(self._tools.values())
        if not tags:
            return specs

        tag_set = set(tags)
        return [spec for spec in specs if tag_set.issubset(set(spec.tags))]

    # pipeline
    def register_pipeline(self, definition: PipelineDefinition) -> None:
        kind, normalized_name = self._parse_lookup_name(definition.name)
        if kind == "tool":
            raise ValueError(
                f"名稱 {definition.name} 使用了 tool 前綴，請改用 register 註冊"
            )

        self._assert_not_duplicated(normalized_name, current_kind="pipeline")
        self._pipelines[normalized_name] = definition
        self._lookup_cache.clear()

    def get_pipeline(self, name: str) -> PipelineDefinition:
        target, normalized_name = self._normalize_lookup_target(name)
        if target not in (None, "pipeline") or normalized_name not in self._pipelines:
            raise KeyError(f"找不到 pipeline {name}")
        return self._pipelines[normalized_name]

    def list_pipelines(self) -> Dict[str, PipelineDefinition]:
        return dict(self._pipelines)

    # Common API
    def get(self, name: str) -> Callable[..., Any]:
        target, normalized_name = self._normalize_lookup_target(name)
        cache_key = (target, normalized_name)
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        if target in (None, "tool") and normalized_name in self._tools:
            func = self._tools[normalized_name].func
            self._lookup_cache[cache_key] = func
            return func
        if target in (None, "pipeline") and normalized_name in self._pipelines:
            func = self._pipelines[normalized_name].func
            self._lookup_cache[cache_key] = func
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

    def _detect_context_argument(self, func: Callable[..., Any]) -> str | None:
        """檢查函式是否需要 PipelineContext 並回傳對應參數名稱。"""

        signature = inspect.signature(func)
        for name, param in signature.parameters.items():
            if is_context_parameter(param):
                return name
        return None

    def _parse_lookup_name(self, name: str) -> Tuple[str | None, str]:
        if not self.enable_type_prefix:
            return None, name

        if name.startswith(self.tool_prefix):
            return "tool", name[len(self.tool_prefix) :]
        if name.startswith(self.pipeline_prefix):
            return "pipeline", name[len(self.pipeline_prefix) :]
        return None, name

    def _normalize_lookup_target(self, name: str) -> Tuple[str | None, str]:
        target, normalized_name = self._parse_lookup_name(name)

        if target is not None:
            return target, normalized_name

        in_tool = normalized_name in self._tools
        in_pipeline = normalized_name in self._pipelines
        if in_tool and in_pipeline:
            raise KeyError(
                f"{normalized_name} 同時存在於工具與 pipeline 中，"\
                f"請使用 {self.tool_prefix}{normalized_name} 或 {self.pipeline_prefix}{normalized_name} 指定目標。"
            )

        if in_tool:
            return "tool", normalized_name
        if in_pipeline:
            return "pipeline", normalized_name

        return None, normalized_name

    def _assert_not_duplicated(self, name: str, *, current_kind: str) -> None:
        if current_kind == "tool" and name in self._tools:
            raise ValueError(f"工具 {name} 已存在")
        if current_kind == "tool" and name in self._pipelines:
            raise ValueError(
                f"名稱 {name} 已被 pipeline 使用，請改用 {self.tool_prefix}{name} 或更換工具名稱。"
            )
        if current_kind == "pipeline" and name in self._pipelines:
            raise ValueError(f"Pipeline {name} 已存在")
        if current_kind == "pipeline" and name in self._tools:
            raise ValueError(
                f"名稱 {name} 已被工具使用，請改用 {self.pipeline_prefix}{name} 或更換 pipeline 名稱。"
            )

        if name in self._tools and name in self._pipelines:
            raise ValueError(
                f"名稱 {name} 已同時註冊為工具與 pipeline，請調整名稱或使用型別前綴分開管理。"
            )

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
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> Any:
        arguments = arguments or {}

        target, normalized_name = self._normalize_lookup_target(name)

        if target == "pipeline" or (
            target is None and normalized_name in self._pipelines
        ):
            definition = self.get_pipeline(normalized_name)
            ctx = self._build_context(user_id=user_id, state_manager=state_manager)
            try:
                return await self._execute_callable(definition.func, ctx, **arguments)
            except Exception:
                if failure_log:
                    failure_log.record_failure(definition.name)
                raise

        func = self.get(name)
        try:
            context_param = context_arg if inject_context else self._detect_context_argument(func)

            if context_param and context_param not in arguments:
                ctx = self._build_context(user_id=user_id, state_manager=state_manager)
                arguments = {context_param: ctx, **arguments}
            return await self._execute_callable(func, **arguments)
        except Exception:
            if failure_log:
                failure_log.record_failure(normalized_name)
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
        inject_context: bool = False,
        context_arg: str = "context",
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
                    inject_context=inject_context,
                    context_arg=context_arg,
                )
            )

        raise RuntimeError(
            "事件迴圈運行時請改用 execute_tool_async 以避免阻塞。"
        )
