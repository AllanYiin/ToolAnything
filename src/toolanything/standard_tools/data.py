"""Dependency-free data transformation standard tools."""
from __future__ import annotations

import csv
import json
import re
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
        """Validate JSON text against a small dependency-free JSON Schema subset."""

        value = json.loads(text)
        schema = json.loads(schema_text)
        errors = validate_json_subset(value, schema)
        return {"valid": not errors, "errors": errors}

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

    for func, name, description in (
        (data_json_parse, "standard.data.json_parse", "Parse JSON text and return the decoded value."),
        (
            data_json_validate,
            "standard.data.json_validate",
            "Validate JSON text against a small dependency-free JSON Schema subset.",
        ),
        (data_csv_inspect, "standard.data.csv_inspect", "Inspect CSV headers, sample rows, and rough shape."),
        (
            data_markdown_extract_links,
            "standard.data.markdown_extract_links",
            "Extract inline Markdown links from text.",
        ),
    ):
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
