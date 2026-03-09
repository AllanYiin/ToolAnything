"""Auth hook interfaces for MCP HTTP transports."""
from __future__ import annotations

from typing import Protocol


class BearerTokenVerifier(Protocol):
    """驗證 Bearer token，回傳對應 user_id。"""

    def verify(self, token: str) -> str | None:
        ...


__all__ = ["BearerTokenVerifier"]
