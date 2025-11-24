"""核心資料模型。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class ToolDefinition:
    path: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.path,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_mcp(self) -> Dict[str, Any]:
        return {
            "name": self.path,
            "description": self.description,
            "input_schema": self.parameters,
        }


@dataclass
class PipelineDefinition:
    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]
    stateful: bool = True

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_mcp(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }
