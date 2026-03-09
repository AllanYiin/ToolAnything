"""非 callable source 的宣告式規格。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class HttpFieldSpec:
    """HTTP input 欄位規格。"""

    name: str
    schema: Dict[str, Any]
    required: bool = False
    source_key: str | None = None

    @property
    def input_key(self) -> str:
        return self.source_key or self.name


@dataclass(frozen=True)
class RetryPolicy:
    """HTTP 重試策略。"""

    max_attempts: int = 1
    backoff_sec: float = 0.0


@dataclass(frozen=True)
class HttpSourceSpec:
    """宣告式 HTTP tool 來源。"""

    name: str
    description: str
    method: str
    base_url: str
    path: str
    path_params: Tuple[HttpFieldSpec, ...] = ()
    query_params: Tuple[HttpFieldSpec, ...] = ()
    body_params: Tuple[HttpFieldSpec, ...] = ()
    header_templates: Dict[str, str] = field(default_factory=dict)
    auth_ref: str | None = None
    timeout_sec: float = 10.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    adapters: Tuple[str, ...] | None = None
    tags: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    strict: bool = True


__all__ = ["HttpFieldSpec", "HttpSourceSpec", "RetryPolicy"]
