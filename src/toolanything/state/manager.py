from __future__ import annotations

from .context import StateContext


class StateManager:
    def __init__(self):
        self.sessions: dict[str, StateContext] = {}

    def get_context(self, user_id: str) -> StateContext:
        if user_id not in self.sessions:
            self.sessions[user_id] = StateContext(user_id)
        return self.sessions[user_id]
