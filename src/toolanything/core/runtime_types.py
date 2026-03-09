"""執行期共用型別。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Protocol

from ..pipeline.context import PipelineContext
from ..state import StateManager


class StreamEmitter(Protocol):
    """串流事件發送介面。"""

    def __call__(self, event: str, payload: Any) -> Awaitable[None] | None:
        ...


@dataclass(frozen=True)
class ExecutionContext:
    """統一的工具執行上下文。"""

    tool_name: str
    user_id: str | None = None
    state_manager: StateManager | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_pipeline_context(self) -> PipelineContext:
        """向下相容地轉成現有 PipelineContext。"""

        return PipelineContext(state_manager=self.state_manager, user_id=self.user_id)


@dataclass(frozen=True)
class InvocationResult:
    """統一的工具執行結果封裝。"""

    output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    streamed: bool = False


__all__ = ["ExecutionContext", "InvocationResult", "StreamEmitter"]
