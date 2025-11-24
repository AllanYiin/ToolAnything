"""Pipeline 執行時的上下文。"""
from __future__ import annotations

from typing import Any, Optional

from toolanything.state.manager import StateManager


class PipelineContext:
    def __init__(self, state_manager: Optional[StateManager], user_id: Optional[str]):
        self.state_manager = state_manager
        self.user_id = user_id or "anonymous"

    def get(self, key: str, default: Any = None) -> Any:
        if self.state_manager is None:
            return default
        return self.state_manager.get(self.user_id).get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self.state_manager is None:
            return
        self.state_manager.set(self.user_id, key, value)
