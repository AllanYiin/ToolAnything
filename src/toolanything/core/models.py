"""核心資料模型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from toolanything.utils.docstring_parser import DocMetadata


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


@dataclass
class ToolDefinition(DefinitionMixin):
    path: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]
    documentation: Optional[DocMetadata] = None

    @property
    def name(self) -> str:
        return self.path


@dataclass
class PipelineDefinition(DefinitionMixin):
    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]
    stateful: bool = True
    documentation: Optional[DocMetadata] = None
