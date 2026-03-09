"""HTTP tool compiler / register API."""
from __future__ import annotations

from typing import Any, Dict

from .credentials import CredentialResolver
from .invokers.http_invoker import HttpInvoker
from .models import ToolSpec
from .registry import ToolRegistry
from .source_specs import HttpFieldSpec, HttpSourceSpec


def _field_schema(field: HttpFieldSpec) -> Dict[str, Any]:
    return dict(field.schema)


def build_http_input_schema(source: HttpSourceSpec) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: list[str] = []

    for field in source.path_params:
        properties[field.input_key] = _field_schema(field)
        if field.required:
            required.append(field.input_key)

    for field in source.query_params:
        properties[field.input_key] = _field_schema(field)
        if field.required:
            required.append(field.input_key)

    if source.body_params:
        body_properties: Dict[str, Any] = {}
        body_required: list[str] = []
        for field in source.body_params:
            body_properties[field.input_key] = _field_schema(field)
            if field.required:
                body_required.append(field.input_key)

        properties["body"] = {
            "type": "object",
            "properties": body_properties,
            "required": body_required,
            "additionalProperties": False,
        }
        if body_required:
            required.append("body")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def compile_http_tool(
    source: HttpSourceSpec,
    *,
    credential_resolver: CredentialResolver | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=source.name,
        description=source.description,
        parameters=build_http_input_schema(source),
        adapters=source.adapters,
        tags=source.tags,
        strict=source.strict,
        metadata=dict(source.metadata),
        source_type="http",
        invoker_id=source.name,
        invoker=HttpInvoker(source, credential_resolver=credential_resolver),
    )


def register_http_tool(
    registry: ToolRegistry,
    source: HttpSourceSpec,
    *,
    credential_resolver: CredentialResolver | None = None,
) -> ToolSpec:
    spec = compile_http_tool(source, credential_resolver=credential_resolver)
    registry.register(spec)
    return spec


__all__ = ["build_http_input_schema", "compile_http_tool", "register_http_tool"]
