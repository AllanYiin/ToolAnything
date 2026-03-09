"""Invoker 核心抽象。"""
from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from ..runtime_types import ExecutionContext, InvocationResult, StreamEmitter


@runtime_checkable
class Invoker(Protocol):
    """所有工具執行體都應遵守的最小介面。"""

    async def invoke(
        self,
        input: Mapping[str, Any] | None,
        context: ExecutionContext,
        stream: StreamEmitter | None = None,
        *,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> InvocationResult:
        ...


__all__ = ["Invoker"]
