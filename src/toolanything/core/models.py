"""核心資料模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from toolanything.utils.docstring_parser import DocMetadata
from toolanything.utils.docstring_parser import parse_docstring
from toolanything.core.schema import build_parameters_schema


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
        return {
            "name": self.name,
            "description": self._compose_description(),
            "input_schema": self.parameters,
        }


@dataclass(frozen=True)
class ToolSpec(DefinitionMixin):
    """標準化的工具描述，作為所有 adapter 的單一資料來源。"""

    name: str
    func: Callable[..., Any]
    description: str
    parameters: Dict[str, Any]
    adapters: Tuple[str, ...] | None = None
    tags: Tuple[str, ...] = ()
    strict: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    documentation: Optional[DocMetadata] = None

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
    ) -> "ToolSpec":
        documentation = parse_docstring(func)
        derived_description = description or (documentation.summary if documentation else None)
        if strict and not derived_description:
            raise ValueError("Tool description is required when strict mode is enabled.")

        params_schema = build_parameters_schema(func)
        return cls(
            name=name or func.__name__,
            func=func,
            description=derived_description or "",
            parameters=params_schema,
            adapters=tuple(adapters) if adapters is not None else None,
            tags=tuple(tags or ()),
            strict=strict,
            metadata=dict(metadata or {}),
            documentation=documentation,
        )


@dataclass
class PipelineDefinition(DefinitionMixin):
    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]
    stateful: bool = True
    documentation: Optional[DocMetadata] = None


# 向後相容：保留舊名稱供既有匯入使用。
ToolDefinition = ToolSpec
