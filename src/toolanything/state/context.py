from __future__ import annotations

from typing import Any


class StateContext:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.data: dict[str, Any] = {}

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def clear(self) -> None:
        self.data.clear()
