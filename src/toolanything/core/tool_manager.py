"""ToolManager: 管理工具註冊、Schema 匯出與統一呼叫入口。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from .models import ToolSpec
from .registry import ToolRegistry


class ToolManager:
    """封裝工具註冊與執行策略的高階介面。"""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        default_adapters: Iterable[str] = ("openai", "mcp"),
        strict: bool = True,
    ) -> None:
        self.registry = registry or ToolRegistry.global_instance()
        self.default_adapters = tuple(default_adapters)
        self.strict = strict
        # 讓 decorator 有機會讀取預設 adapter 設定。
        self.registry.default_adapters = self.default_adapters  # type: ignore[attr-defined]

    def register(self, func: Callable[..., Any] | None = None, **tool_kwargs: Any):
        """同時支援 decorator 與手動註冊的介面。"""

        def decorator(fn: Callable[..., Any]):
            spec = ToolSpec.from_function(
                fn,
                name=tool_kwargs.get("name"),
                description=tool_kwargs.get("description"),
                adapters=tool_kwargs.get("adapters", self.default_adapters),
                tags=tool_kwargs.get("tags"),
                strict=tool_kwargs.get("strict", self.strict),
                metadata=tool_kwargs.get("metadata"),
            )
            self.registry.register(spec)
            return fn

        if func is not None:
            return decorator(func)

        return decorator

    def _filter_specs(self, adapter: str) -> List[ToolSpec]:
        return [
            spec
            for spec in self.registry.list()
            if spec.adapters is None or adapter in spec.adapters
        ]

    def get_schema(self, adapter: str) -> List[Dict[str, Any]]:
        adapter_lower = adapter.lower()
        specs = self._filter_specs(adapter_lower)

        if adapter_lower == "openai":
            return [spec.to_openai() for spec in specs]
        if adapter_lower == "mcp":
            return [spec.to_mcp() for spec in specs]

        raise ValueError(f"未知 adapter: {adapter}")

    async def invoke(
        self,
        name: str,
        args: Dict[str, Any],
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """統一的 async 呼叫入口，兼容同步函數。"""

        # context 可作為未來擴充，暫不強制注入。
        context = context or {}
        return await self.registry.execute_tool_async(
            name,
            arguments=args,
            user_id=context.get("user_id"),
            state_manager=context.get("state_manager"),
        )
