"""核心資料模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from ..state import StateManager
from ..utils.docstring_parser import DocMetadata
from ..utils.docstring_parser import parse_docstring
from ..utils.openai_tool_names import build_openai_name_mappings
from .invokers import CallableInvoker, Invoker
from .schema import build_parameters_schema, to_openai_strict_schema
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

    def to_openai(
        self,
        *,
        name: str | None = None,
        parameters: Dict[str, Any] | None = None,
        strict: bool | None = None,
    ) -> Dict[str, Any]:
        active_strict = bool(getattr(self, "strict", False)) if strict is None else strict
        active_parameters = parameters or self.parameters
        if active_strict:
            active_parameters = to_openai_strict_schema(active_parameters)
        openai_name = name or build_openai_name_mappings([self.name])[0][self.name]
        return {
            "type": "function",
            "function": {
                "name": openai_name,
                "description": self._compose_description(),
                "parameters": active_parameters,
                "strict": active_strict,
            },
        }

    def to_mcp(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "description": self._compose_description(),
            "inputSchema": self.parameters,
        }
        metadata = getattr(self, "metadata", {}) or {}
        title = metadata.get("title")
        if isinstance(title, str) and title.strip():
            payload["title"] = title.strip()
        output_schema = metadata.get("output_schema") or metadata.get("mcp_output_schema")
        if isinstance(output_schema, dict) and output_schema:
            payload["outputSchema"] = dict(output_schema)
        annotations = metadata.get("mcp_annotations")
        if isinstance(annotations, dict) and annotations:
            payload["annotations"] = dict(annotations)
        execution = metadata.get("mcp_execution")
        if isinstance(execution, dict) and execution:
            payload["execution"] = dict(execution)
        meta = metadata.get("mcp_meta")
        if isinstance(meta, dict) and meta:
            payload["_meta"] = dict(meta)
        return payload

    def to_cli(self) -> Dict[str, Any]:
        metadata = getattr(self, "metadata", {}) or {}
        raw_cli = metadata.get("cli")
        cli = dict(raw_cli) if isinstance(raw_cli, dict) else {}
        command_path = _cli_command_path_from_metadata(cli) or _default_cli_command_path(self.name)
        aliases = [str(alias) for alias in cli.get("aliases", []) if str(alias).strip()] if isinstance(cli.get("aliases"), list) else []
        examples = [str(example) for example in cli.get("examples", []) if str(example).strip()] if isinstance(cli.get("examples"), list) else []
        argument_metadata = cli.get("arguments") if isinstance(cli.get("arguments"), dict) else {}
        properties = self.parameters.get("properties", {}) if isinstance(self.parameters, dict) else {}
        required = set(self.parameters.get("required", [])) if isinstance(self.parameters, dict) else set()
        arguments: dict[str, Any] = {}
        if isinstance(properties, dict):
            for argument_name, schema in properties.items():
                raw_arg_meta = argument_metadata.get(argument_name, {}) if isinstance(argument_metadata, dict) else {}
                arg_meta = dict(raw_arg_meta) if isinstance(raw_arg_meta, dict) else {}
                option = "--" + str(argument_name).replace("_", "-")
                arguments[str(argument_name)] = {
                    "name": str(argument_name),
                    "optionStrings": [option],
                    "schema": dict(schema) if isinstance(schema, dict) else {},
                    "required": argument_name in required,
                    "pathLike": bool(arg_meta.get("path_like", False)),
                    "inputMode": arg_meta.get("input_mode", "scalar"),
                }
        return {
            "name": self.name,
            "description": self._compose_description(),
            "commandPath": command_path,
            "aliases": aliases,
            "summary": str(cli.get("summary") or self.description),
            "examples": examples,
            "hidden": bool(cli.get("hidden", False)),
            "sourceType": getattr(self, "source_type", "callable"),
            "arguments": arguments,
            "metadata": cli,
        }


def _default_cli_command_path(tool_name: str) -> list[str]:
    parts = [part for part in tool_name.split(".") if part]
    return [_normalize_cli_segment(part) for part in parts] or ["tool"]


def _cli_command_path_from_metadata(cli: Dict[str, Any]) -> list[str]:
    command_path = cli.get("command_path")
    if isinstance(command_path, list):
        return [_normalize_cli_segment(str(part)) for part in command_path if str(part).strip()]
    command = cli.get("command")
    if isinstance(command, str):
        return [_normalize_cli_segment(part) for part in command.split() if part.strip()]
    return []


def _normalize_cli_segment(segment: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", segment.strip()).strip("-").lower()
    return slug or "tool"


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
