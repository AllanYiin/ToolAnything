"""多使用者狀態管理。"""
from __future__ import annotations

from typing import Any, Dict


class StateManager:
    def __init__(self) -> None:
        self._storage: Dict[str, Dict[str, Any]] = {}

    def get(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._storage:
            self._storage[user_id] = {}
        return self._storage[user_id]

    def set(self, user_id: str, key: str, value: Any) -> None:
        bucket = self.get(user_id)
        bucket[key] = value

    def clear(self, user_id: str) -> None:
        self._storage[user_id] = {}

    def clear_all(self) -> None:
        self._storage = {}
