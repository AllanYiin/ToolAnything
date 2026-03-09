"""SQL tool compiler / register API."""
from __future__ import annotations

from typing import Dict

from .invokers.sql_invoker import SqlInvoker, extract_sql_params
from .models import ToolSpec
from .registry import ToolRegistry
from .source_specs import SqlSourceSpec
from .sql_connections import InMemorySQLConnectionProvider, SQLConnectionProvider


def build_sql_input_schema(source: SqlSourceSpec) -> Dict[str, object]:
    properties: Dict[str, object] = {}
    required: list[str] = []

    for param_name in extract_sql_params(source.query_template):
        properties[param_name] = dict(source.param_schemas.get(param_name, {"type": "string"}))
        required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def compile_sql_tool(
    source: SqlSourceSpec,
    *,
    connection_provider: SQLConnectionProvider | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=source.name,
        description=source.description,
        parameters=build_sql_input_schema(source),
        adapters=source.adapters,
        tags=source.tags,
        strict=source.strict,
        metadata=dict(source.metadata),
        source_type="sql",
        invoker_id=source.name,
        invoker=SqlInvoker(
            source,
            connection_provider=connection_provider or InMemorySQLConnectionProvider(),
        ),
    )


def register_sql_tool(
    registry: ToolRegistry,
    source: SqlSourceSpec,
    *,
    connection_provider: SQLConnectionProvider | None = None,
) -> ToolSpec:
    spec = compile_sql_tool(source, connection_provider=connection_provider)
    registry.register(spec)
    return spec


__all__ = ["build_sql_input_schema", "compile_sql_tool", "register_sql_tool"]
