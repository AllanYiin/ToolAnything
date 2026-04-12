"""核心資料模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from ..state import StateManager
from ..utils.docstring_parser import DocMetadata
from ..utils.docstring_parser import parse_docstring
from .invokers import CallableInvoker, Invoker
from .schema import build_parameters_schema
from .metadata import ToolMetadata, normalize_metadata


def _derive_default_name(func: Callable[..., Any]) -> str:
    """推導工具的預設名稱，優先使用類別與方法名稱。"""

    qualname = getattr(func, "__qualname__", "") or ""
    if "." in qualname:
        segments = [segment for segment in qualname.split(".") if segment != "<locals>"]
        if len(segments) >= 2:
            return ".".join(segments[-2:])
    return getattr(func, "__name__", "")


def _merge_cli_metadata(
    metadata: Dict[str, Any] | None,
    cli_command: str | None,
) -> Dict[str, Any]:
    merged = dict(metadata or {})
    if not cli_command:
        return merged

    raw_cli = merged.get("cli")
    cli_metadata = dict(raw_cli) if isinstance(raw_cli, dict) else {}
    cli_metadata.setdefault("command", cli_command)
    merged["cli"] = cli_metadata
    return merged


class DefinitionMixin:
    """工具與 Pipeline 的共用基底類別 (Mixin)。"""

    # 這些欄位將由子類別 (dataclass) 定義
    # description: str
    # parameters: Dict[str, Any]
    # documentation: Optional[DocMetadata]

    # @property
    # def name(self) -> str:
    #     """取得名稱，子類別需實作或透過欄位提供。"""
    #     raise NotImplementedError

    def _compose_description(self) -> str:
        if self.documentation is None:
            return self.description

        prompt_hint = self.documentation.to_prompt_hint()
        if not prompt_hint:
            return self.description
        return f"{self.description} {prompt_hint}".strip()

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self._compose_description(),
                "parameters": self.parameters,
            },
        }

    def to_mcp(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "description": self._compose_description(),
            "input_schema": self.parameters,
        }
        metadata = getattr(self, "metadata", {}) or {}
        annotations = metadata.get("mcp_annotations")
        if isinstance(annotations, dict) and annotations:
            payload["annotations"] = dict(annotations)
        return payload


@dataclass(frozen=True)
class ToolContract(DefinitionMixin):
    """工具契約：對外 schema 與 metadata 的穩定視圖。"""

    name: str
    description: str
    parameters: Dict[str, Any]
    adapters: Tuple[str, ...] | None = None
    tags: Tuple[str, ...] = ()
    strict: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    documentation: Optional[DocMetadata] = None
    source_type: str = "callable"
    invoker_id: str | None = None


@dataclass(frozen=True)
class ToolSpec(ToolContract):
    """標準化工具描述。

    核心已改為 invoker-first；`func` 仍保留作為 compatibility layer。
    """

    func: Callable[..., Any] | None = field(default=None, repr=False, compare=False)
    invoker: Invoker | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.invoker is None and self.func is None:
            raise ValueError("ToolSpec 必須至少提供 func 或 invoker。")

        if self.invoker is None and self.func is not None:
            object.__setattr__(self, "invoker", CallableInvoker(self.func))

        if self.func is None and isinstance(self.invoker, CallableInvoker):
            object.__setattr__(self, "func", self.invoker.func)

        if self.invoker_id is None and self.invoker is not None:
            object.__setattr__(self, "invoker_id", self.name)

    @property
    def contract(self) -> ToolContract:
        """回傳不含 execution body 的契約視圖。"""

        return ToolContract(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            adapters=self.adapters,
            tags=self.tags,
            strict=self.strict,
            metadata=dict(self.metadata),
            documentation=self.documentation,
            source_type=self.source_type,
            invoker_id=self.invoker_id,
        )

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        adapters: list[str] | Tuple[str, ...] | None = None,
        tags: list[str] | Tuple[str, ...] | None = None,
        strict: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        cli_command: str | None = None,
    ) -> "ToolSpec":
        normalized_func = getattr(func, "__func__", func)
        documentation = parse_docstring(normalized_func)
        derived_description = description or (documentation.summary if documentation else None)
        if strict and not derived_description:
            raise ValueError("Tool description is required when strict mode is enabled.")

        params_schema = build_parameters_schema(normalized_func)
        invoker = CallableInvoker(func)
        return cls(
            name=name or _derive_default_name(normalized_func),
            description=derived_description or "",
            parameters=params_schema,
            adapters=tuple(adapters) if adapters is not None else None,
            tags=tuple(tags or ()),
            strict=strict,
            metadata=_merge_cli_metadata(metadata, cli_command),
            documentation=documentation,
            source_type="callable",
            invoker_id=name or _derive_default_name(normalized_func),
            func=func,
            invoker=invoker,
        )

    @property
    def tool_metadata(self) -> ToolMetadata:
        """回傳正規化後的 metadata 視圖。"""

        return normalize_metadata(self.metadata, tags=self.tags)

    def normalized_metadata(self) -> ToolMetadata:
        """向下相容的 metadata 視圖方法。"""

        return self.tool_metadata


@dataclass
class PipelineDefinition(DefinitionMixin):
    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]
    stateful: bool = True
    state_manager: Optional[StateManager] = None
    documentation: Optional[DocMetadata] = None


# 向後相容：保留舊名稱供既有匯入使用。
ToolDefinition = ToolSpec
