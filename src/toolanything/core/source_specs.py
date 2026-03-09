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


@dataclass(frozen=True)
class SqlSourceSpec:
    """宣告式 SQL tool 來源。"""

    name: str
    description: str
    connection_ref: str
    query_template: str
    read_only: bool = True
    timeout_sec: float = 5.0
    max_rows: int = 100
    adapters: Tuple[str, ...] | None = None
    tags: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    strict: bool = True
    param_schemas: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSourceSpec:
    """宣告式 model inference tool 來源。"""

    name: str
    description: str
    model_type: str
    input_spec: Dict[str, Dict[str, Any]]
    output_spec: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    artifact_path: str | None = None
    model_ref: str | None = None
    preprocessor_ref: str | None = None
    postprocessor_ref: str | None = None
    device: str = "cpu"
    timeout_sec: float = 5.0
    adapters: Tuple[str, ...] | None = None
    tags: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    strict: bool = True


__all__ = [
    "HttpFieldSpec",
    "HttpSourceSpec",
    "RetryPolicy",
    "SqlSourceSpec",
    "ModelSourceSpec",
]
