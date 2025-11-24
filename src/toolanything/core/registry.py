"""工具與 pipeline 註冊中心。"""
from __future__ import annotations

from typing import Any, Callable, Dict

from .models import PipelineDefinition, ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._pipelines: Dict[str, PipelineDefinition] = {}

    # 工具
    def register_tool(self, definition: ToolDefinition) -> None:
        if definition.path in self._tools:
            raise ValueError(f"工具 {definition.path} 已存在")
        self._tools[definition.path] = definition

    def get_tool(self, path: str) -> ToolDefinition:
        if path not in self._tools:
            raise KeyError(f"找不到工具 {path}")
        return self._tools[path]

    def list_tools(self) -> Dict[str, ToolDefinition]:
        return dict(self._tools)

    # pipeline
    def register_pipeline(self, definition: PipelineDefinition) -> None:
        if definition.name in self._pipelines:
            raise ValueError(f"Pipeline {definition.name} 已存在")
        self._pipelines[definition.name] = definition

    def get_pipeline(self, name: str) -> PipelineDefinition:
        if name not in self._pipelines:
            raise KeyError(f"找不到 pipeline {name}")
        return self._pipelines[name]

    def list_pipelines(self) -> Dict[str, PipelineDefinition]:
        return dict(self._pipelines)

    # Common API
    def get(self, name: str) -> Callable[..., Any]:
        if name in self._tools:
            return self._tools[name].func
        if name in self._pipelines:
            return self._pipelines[name].func
        raise KeyError(f"找不到 {name}")

    def to_openai_tools(self) -> list[dict[str, Any]]:
        entries = [definition.to_openai() for definition in self._tools.values()]
        entries += [definition.to_openai() for definition in self._pipelines.values()]
        return entries

    def to_mcp_tools(self) -> list[dict[str, Any]]:
        entries = [definition.to_mcp() for definition in self._tools.values()]
        entries += [definition.to_mcp() for definition in self._pipelines.values()]
        return entries
