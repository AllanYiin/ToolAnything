"""JSON Schema -> argparse 參數映射。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .exceptions import CLIArgumentValidationError
from .types import CLIArgumentSpec
from ..core.models import ToolSpec


PATH_HINT_TOKENS = ("path", "file", "image", "pdf", "document")


def _bool_from_string(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise CLIArgumentValidationError(f"無法解析布林值: {value}")


def _json_or_file(value: str) -> Any:
    if value.startswith("@"):
        path = Path(value[1:])
        if not path.exists():
            raise CLIArgumentValidationError(f"找不到 JSON 檔案: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise CLIArgumentValidationError(f"JSON 解析失敗: {exc.msg}") from exc


def _resolve_effective_schema(schema: dict[str, Any]) -> dict[str, Any]:
    for keyword in ("oneOf", "anyOf"):
        variants = schema.get(keyword)
        if not isinstance(variants, list):
            continue
        non_null_variants = [variant for variant in variants if variant.get("type") != "null"]
        if len(non_null_variants) != 1 or len(non_null_variants) == len(variants):
            continue

        merged = dict(non_null_variants[0])
        for key in ("default", "description", "enum"):
            if key in schema and key not in merged:
                merged[key] = schema[key]
        return merged
    return schema


def _infer_path_like(name: str, schema: dict[str, Any], help_text: str | None) -> bool:
    effective_schema = _resolve_effective_schema(schema)
    if effective_schema.get("format") in {"path", "file-path"}:
        return True
    description = (effective_schema.get("description") or help_text or "").lower()
    lowered_name = name.lower()
    return any(token in lowered_name or token in description for token in PATH_HINT_TOKENS)


def _schema_kind(schema: dict[str, Any]) -> str:
    effective_schema = _resolve_effective_schema(schema)
    schema_type = effective_schema.get("type")
    if schema_type == "array":
        return "array"
    if schema_type == "object" or effective_schema.get("properties") or effective_schema.get("additionalProperties"):
        return "object"
    if schema_type == "boolean":
        return "boolean"
    return "scalar"


def _scalar_type(schema: dict[str, Any]):
    schema_type = _resolve_effective_schema(schema).get("type")
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return _bool_from_string
    return str


def build_argument_specs(tool: ToolSpec) -> list[CLIArgumentSpec]:
    properties = tool.parameters.get("properties", {})
    required_set = set(tool.parameters.get("required", []))
    parameter_help = tool.documentation.parameters if tool.documentation else {}
    specs: list[CLIArgumentSpec] = []

    for name, schema in properties.items():
        option_name = f"--{name.replace('_', '-')}"
        help_text = parameter_help.get(name) or schema.get("description")
        specs.append(
            CLIArgumentSpec(
                name=name,
                option_strings=(option_name,),
                schema=dict(schema),
                required=name in required_set,
                help_text=help_text,
                kind=_schema_kind(schema),
                path_like=_infer_path_like(name, schema, help_text),
            )
        )
    return specs


def add_argument_to_parser(parser: argparse.ArgumentParser, arg_spec: CLIArgumentSpec) -> None:
    kwargs: dict[str, Any] = {
        "dest": arg_spec.dest,
        "help": arg_spec.help_text,
    }
    schema = arg_spec.schema
    effective_schema = _resolve_effective_schema(schema)
    kind = arg_spec.kind

    if "enum" in effective_schema:
        kwargs["choices"] = list(effective_schema["enum"])

    if kind == "array":
        item_schema = effective_schema.get("items", {})
        kwargs["action"] = "append"
        kwargs["type"] = _scalar_type(item_schema)
        kwargs["required"] = arg_spec.required
        parser.add_argument(*arg_spec.option_strings, **kwargs)
        return

    if kind == "object":
        kwargs["type"] = _json_or_file
        kwargs["required"] = arg_spec.required
        kwargs["metavar"] = "JSON|@FILE"
        parser.add_argument(*arg_spec.option_strings, **kwargs)
        return

    if effective_schema.get("type") == "boolean":
        default = schema.get("default", effective_schema.get("default", None))
        if default is True:
            parser.add_argument(
                f"--no-{arg_spec.name.replace('_', '-')}",
                dest=arg_spec.dest,
                action="store_false",
                help=arg_spec.help_text,
            )
            parser.set_defaults(**{arg_spec.dest: True})
            return
        if default is False or default is None:
            parser.add_argument(
                *arg_spec.option_strings,
                dest=arg_spec.dest,
                action="store_true",
                help=arg_spec.help_text,
                required=False,
            )
            if default is not None:
                parser.set_defaults(**{arg_spec.dest: False})
            return

    kwargs["type"] = _scalar_type(effective_schema)
    if "default" in schema:
        kwargs["default"] = schema["default"]
    elif arg_spec.required:
        kwargs["required"] = True
    parser.add_argument(*arg_spec.option_strings, **kwargs)


def parse_tool_arguments(namespace: argparse.Namespace, arg_specs: list[CLIArgumentSpec]) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    for spec in arg_specs:
        value = getattr(namespace, spec.dest, None)
        if value is None:
            continue
        arguments[spec.name] = value
    return arguments
