"""Dependency-free data transformation standard tools."""
from __future__ import annotations

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

from toolanything.core import ToolRegistry, ToolSpec

from .options import StandardToolOptions
from .registration import positive_limit, register_callable


def register_data_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    del options
    specs: list[ToolSpec] = []

    def data_json_parse(text: str) -> dict[str, Any]:
        """Parse JSON text and return the decoded value."""

        value = json.loads(text)
        return {"ok": True, "value": value, "type": type(value).__name__}

    def data_json_validate(text: str, schema_text: str) -> dict[str, Any]:
        """Validate JSON text against JSON Schema, using jsonschema when installed."""

        value = json.loads(text)
        schema = json.loads(schema_text)
        errors, validator = validate_json(value, schema)
        return {"valid": not errors, "errors": errors, "validator": validator}

    def data_csv_inspect(text: str, delimiter: str = ",", limit: int = 20) -> dict[str, Any]:
        """Inspect CSV headers, sample rows, and rough shape without writing files."""

        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        rows = list(reader)
        sample_limit = positive_limit(limit, default=20)
        headers = rows[0] if rows else []
        data_rows = rows[1:] if rows else []
        width = max((len(row) for row in rows), default=0)
        return {
            "headers": headers,
            "row_count": len(data_rows),
            "column_count": width,
            "sample_rows": data_rows[:sample_limit],
            "truncated": len(data_rows) > sample_limit,
        }

    def data_markdown_extract_links(text: str, limit: int = 100) -> dict[str, Any]:
        """Extract inline Markdown links from text."""

        max_items = positive_limit(limit, default=100)
        links = [
            {"label": match.group(1), "url": match.group(2)}
            for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text)
        ]
        return {"links": links[:max_items], "truncated": len(links) > max_items}

    def data_jsonl_inspect(text: str, limit: int = 20) -> dict[str, Any]:
        """Inspect JSON Lines text and return sample values and parse errors."""

        max_items = positive_limit(limit, default=20)
        rows = []
        errors = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if len(rows) < max_items:
                    rows.append(value)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_number, "message": exc.msg})
        return {
            "record_count": sum(1 for line in text.splitlines() if line.strip()) - len(errors),
            "sample_records": rows,
            "errors": errors[:max_items],
            "truncated": len(rows) >= max_items or len(errors) > max_items,
        }

    def data_toml_parse(text: str) -> dict[str, Any]:
        """Parse TOML text with stdlib tomllib or optional tomli."""

        value = parse_toml(text)
        return {"ok": True, "value": value}

    def data_yaml_parse(text: str) -> dict[str, Any]:
        """Parse YAML text when PyYAML is installed."""

        value = parse_yaml(text)
        return {"ok": True, "value": value}

    def data_xml_inspect(text: str, limit: int = 50) -> dict[str, Any]:
        """Safely inspect XML root, attributes, and child tags."""

        max_items = positive_limit(limit, default=50)
        root = ET.fromstring(text)
        children = [{"tag": child.tag, "attributes": dict(child.attrib)} for child in list(root)[:max_items]]
        return {
            "root_tag": root.tag,
            "root_attributes": dict(root.attrib),
            "children": children,
            "child_count": len(list(root)),
            "truncated": len(list(root)) > max_items,
        }

    tool_specs = (
        (
            data_json_parse,
            "standard.data.json_parse",
            "Parse JSON text and return the decoded value.",
            {"text": {"input_mode": "text_or_file"}},
        ),
        (
            data_json_validate,
            "standard.data.json_validate",
            "Validate JSON text against a small dependency-free JSON Schema subset.",
            {
                "text": {"input_mode": "text_or_file"},
                "schema_text": {"input_mode": "text_or_file"},
            },
        ),
        (
            data_csv_inspect,
            "standard.data.csv_inspect",
            "Inspect CSV headers, sample rows, and rough shape.",
            {"text": {"input_mode": "text_or_file"}},
        ),
        (
            data_markdown_extract_links,
            "standard.data.markdown_extract_links",
            "Extract inline Markdown links from text.",
            {"text": {"input_mode": "text_or_file"}},
        ),
        (
            data_jsonl_inspect,
            "standard.data.jsonl_inspect",
            "Inspect JSON Lines text and return sample records and parse errors.",
            {"text": {"input_mode": "text_or_file"}},
        ),
        (
            data_toml_parse,
            "standard.data.toml_parse",
            "Parse TOML text with stdlib tomllib or optional tomli.",
            {"text": {"input_mode": "text_or_file"}},
        ),
        (
            data_yaml_parse,
            "standard.data.yaml_parse",
            "Parse YAML text when PyYAML is installed.",
            {"text": {"input_mode": "text_or_file"}},
        ),
        (
            data_xml_inspect,
            "standard.data.xml_inspect",
            "Safely inspect XML root, attributes, and child tags.",
            {"text": {"input_mode": "text_or_file"}},
        ),
    )
    for func, name, description, cli_arguments in tool_specs:
        specs.append(
            register_callable(
                active_registry,
                func,
                name=name,
                description=description,
                category="data",
                scopes=("data:transform",),
                read_only=True,
                open_world=False,
                cli_arguments=cli_arguments,
            )
        )
    return specs


def validate_json_subset(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not json_type_matches(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
        return errors

    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path}.{field}: required")
        properties = schema.get("properties", {})
        if isinstance(properties, Mapping):
            for field, field_schema in properties.items():
                if field in value and isinstance(field_schema, Mapping):
                    errors.extend(validate_json_subset(value[field], field_schema, f"{path}.{field}"))

    if isinstance(value, list) and isinstance(schema.get("items"), Mapping):
        item_schema = schema["items"]
        for index, item in enumerate(value):
            errors.extend(validate_json_subset(item, item_schema, f"{path}[{index}]"))
    return errors


def json_type_matches(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(json_type_matches(value, item) for item in expected_type)
    if expected_type == "null":
        return value is None
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    mapping = {
        "array": list,
        "boolean": bool,
        "object": dict,
        "string": str,
    }
    target = mapping.get(expected_type)
    return isinstance(value, target) if target else True


def validate_json(value: Any, schema: Mapping[str, Any]) -> tuple[list[str], str]:
    try:
        from jsonschema import validators  # type: ignore[import-not-found]
    except ImportError:
        return validate_json_subset(value, schema), "subset"

    try:
        validator_cls = validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
        return [format_jsonschema_error(error) for error in errors], validator_cls.__name__
    except Exception as exc:
        return [f"$: schema validation setup failed: {exc}"], "jsonschema"


def format_jsonschema_error(error: Any) -> str:
    try:
        path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path)
        return f"{path}: {error.message}"
    except Exception:
        return str(error)


def parse_toml(text: str) -> Any:
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(text)
    try:
        import tomli  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("TOML parsing requires Python 3.11+ or optional dependency 'tomli'") from exc
    return tomli.loads(text)


def parse_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("YAML parsing requires optional dependency 'PyYAML'") from exc
    return yaml.safe_load(text)
