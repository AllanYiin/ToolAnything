"""工具與 pipeline 註冊中心。"""
from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from .failure_log import FailureLogManager
from .invokers import CallableInvoker, Invoker
from .models import PipelineDefinition, ToolSpec
from .runtime_types import ExecutionContext, StreamEmitter
from ..state import StateManager


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
        self._invokers: Dict[str, Invoker] = {}
        self._pipelines: Dict[str, PipelineDefinition] = {}
        self._pipeline_invokers: Dict[str, CallableInvoker] = {}
        self._lookup_cache: Dict[
            Tuple[str | None, str], Tuple[str, ToolSpec | PipelineDefinition]
        ] = {}
        self._observers: list[Any] = []

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
        if spec.invoker is None:
            raise ValueError(f"工具 {spec.name} 缺少 invoker，無法註冊。")
        self._invokers[normalized_name] = spec.invoker
        self._lookup_cache.clear()
        self._notify_observers("on_tool_registered", spec)

    # 舊介面的相容別名
    def register_tool(self, definition: ToolSpec) -> None:
        self.register(definition)

    def unregister(self, name: str) -> None:
        target, normalized_name = self._normalize_lookup_target(name)
        if target not in (None, "tool") or normalized_name not in self._tools:
            raise KeyError(f"找不到工具 {name}")
        del self._tools[normalized_name]
        self._invokers.pop(normalized_name, None)
        self._lookup_cache.clear()
        self._notify_observers("on_tool_unregistered", normalized_name)

    def get_tool(self, name: str) -> ToolSpec:
        target, normalized_name = self._normalize_lookup_target(name)
        if target not in (None, "tool") or normalized_name not in self._tools:
            raise KeyError(f"找不到工具 {name}")
        return self._tools[normalized_name]

    def get_tool_contract(self, name: str) -> ToolSpec:
        target, normalized_name = self._normalize_lookup_target(name)
        if target not in (None, "tool") or normalized_name not in self._tools:
            raise KeyError(f"找不到工具 {name}")
        return self._tools[normalized_name]

    def get_invoker(self, name: str) -> Invoker:
        target, normalized_name = self._normalize_lookup_target(name)
        if target not in (None, "tool") or normalized_name not in self._invokers:
            raise KeyError(f"找不到工具 invoker {name}")
        return self._invokers[normalized_name]

    def list(self, *, tags: Optional[List[str]] = None) -> List[ToolSpec]:
        specs = list(self._tools.values())
        if not tags:
            return specs

        tag_set = set(tags)
        return [spec for spec in specs if tag_set.issubset(set(spec.tags))]

    def add_observer(self, observer: Any) -> None:
        if observer in self._observers:
            return
        self._observers.append(observer)

    def remove_observer(self, observer: Any) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

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
    def _resolve_lookup(self, name: str) -> Tuple[str, ToolSpec | PipelineDefinition]:
        target, normalized_name = self._normalize_lookup_target(name)
        cache_key = (target, normalized_name)
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]

        if target in (None, "tool") and normalized_name in self._tools:
            lookup = ("tool", self._tools[normalized_name])
            self._lookup_cache[cache_key] = lookup
            return lookup
        if target in (None, "pipeline") and normalized_name in self._pipelines:
            lookup = ("pipeline", self._pipelines[normalized_name])
            self._lookup_cache[cache_key] = lookup
            return lookup

        raise KeyError(f"找不到 {name}")

    def get(self, name: str) -> Any:
        """向下相容：對 callable-backed tool/pipeline 回傳可呼叫物件。"""

        lookup_kind, definition = self._resolve_lookup(name)

        if lookup_kind == "tool":
            func = definition.func
            if func is None:
                raise TypeError(f"工具 {definition.name} 並非 callable-backed tool，請改用 get_invoker().")
            return func

        return definition.func

    def to_openai_tools(self, *, adapter: str | None = None) -> list[dict[str, Any]]:
        entries = [
            definition.contract.to_openai()
            for definition in self._tools.values()
            if adapter is None
            or definition.adapters is None
            or adapter in definition.adapters
        ]
        entries += [definition.to_openai() for definition in self._pipelines.values()]
        return entries

    def to_mcp_tools(self, *, adapter: str | None = None) -> list[dict[str, Any]]:
        entries = [
            definition.contract.to_mcp()
            for definition in self._tools.values()
            if adapter is None
            or definition.adapters is None
            or adapter in definition.adapters
        ]
        entries += [definition.to_mcp() for definition in self._pipelines.values()]
        return entries

    def _build_context(
        self, *, user_id: str | None, state_manager: StateManager | None
    ) -> ExecutionContext:
        return ExecutionContext(tool_name="", state_manager=state_manager, user_id=user_id)

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

    def _notify_observers(self, method_name: str, payload: Any) -> None:
        for observer in list(self._observers):
            method = getattr(observer, method_name, None)
            if callable(method):
                method(payload)

    async def invoke_tool_async(
        self,
        name: str,
        *,
        arguments: Dict[str, Any] | None = None,
        user_id: str | None = None,
        state_manager: StateManager | None = None,
        failure_log: FailureLogManager | None = None,
        stream: StreamEmitter | None = None,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> Any:
        arguments = arguments or {}
        lookup_kind, definition = self._resolve_lookup(name)

        try:
            if lookup_kind == "pipeline":
                active_state_manager = state_manager or definition.state_manager
                invoker = self._pipeline_invokers.setdefault(
                    definition.name,
                    CallableInvoker(definition.func),
                )
                context = ExecutionContext(
                    tool_name=definition.name,
                    user_id=user_id,
                    state_manager=active_state_manager,
                )
                result = await invoker.invoke(
                    arguments,
                    context,
                    stream=stream,
                    inject_context=inject_context,
                    context_arg=context_arg,
                )
                return result.output

            invoker = self.get_invoker(definition.name)
            context = ExecutionContext(
                tool_name=definition.name,
                user_id=user_id,
                state_manager=state_manager,
            )
            result = await invoker.invoke(
                arguments,
                context,
                stream=stream,
                inject_context=inject_context,
                context_arg=context_arg,
            )
            return result.output
        except Exception:
            if failure_log:
                failure_log.record_failure(definition.name)
            raise

    async def execute_tool_async(
        self,
        name: str,
        *,
        arguments: Dict[str, Any] | None = None,
        user_id: str | None = None,
        state_manager: StateManager | None = None,
        failure_log: FailureLogManager | None = None,
        stream: StreamEmitter | None = None,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> Any:
        return await self.invoke_tool_async(
            name,
            arguments=arguments,
            user_id=user_id,
            state_manager=state_manager,
            failure_log=failure_log,
            stream=stream,
            inject_context=inject_context,
            context_arg=context_arg,
        )

    def execute_tool(
        self,
        name: str,
        *,
        arguments: Dict[str, Any] | None = None,
        user_id: str | None = None,
        state_manager: StateManager | None = None,
        failure_log: FailureLogManager | None = None,
        stream: StreamEmitter | None = None,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> Any:
        """同步介面：在未啟動事件迴圈時執行，否則要求使用 async 版本。"""

        try:
            import asyncio

            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.invoke_tool_async(
                    name,
                    arguments=arguments,
                    user_id=user_id,
                    state_manager=state_manager,
                    failure_log=failure_log,
                    stream=stream,
                    inject_context=inject_context,
                    context_arg=context_arg,
                )
            )

        raise RuntimeError(
            "事件迴圈運行時請改用 execute_tool_async 以避免阻塞。"
        )
