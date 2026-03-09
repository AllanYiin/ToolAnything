"""Model tool compiler / register API."""
from __future__ import annotations

from typing import Any, Dict

from .invokers.model_invoker import ModelInvoker
from .model_runtime import ModelHookRegistry, ModelSessionCache
from .models import ToolSpec
from .registry import ToolRegistry
from .source_specs import ModelSourceSpec


def _schema_from_input_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    kind = spec.get("kind", "tensor")
    dtype = spec.get("dtype", "float32")
    shape = spec.get("shape", [])

    if kind == "tensor":
        if len(shape) == 1 and shape[0] not in (None, -1):
            item_type = "number" if "float" in str(dtype) else "integer"
            return {
                "type": "array",
                "items": {"type": item_type},
                "minItems": shape[0],
                "maxItems": shape[0],
            }
        return {"type": "array"}

    if kind == "text":
        return {"type": "string"}
    if kind == "image":
        return {"type": "string", "description": "Base64 encoded image"}
    if kind == "tabular":
        return {"type": "array", "items": {"type": "object"}}
    return {"type": "object"}


def build_model_input_schema(source: ModelSourceSpec) -> Dict[str, Any]:
    properties = {
        name: _schema_from_input_spec(spec)
        for name, spec in source.input_spec.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(source.input_spec.keys()),
        "additionalProperties": False,
    }


def compile_model_tool(
    source: ModelSourceSpec,
    *,
    session_cache: ModelSessionCache | None = None,
    hook_registry: ModelHookRegistry | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=source.name,
        description=source.description,
        parameters=build_model_input_schema(source),
        adapters=source.adapters,
        tags=source.tags,
        strict=source.strict,
        metadata=dict(source.metadata),
        source_type=source.model_type,
        invoker_id=source.name,
        invoker=ModelInvoker(
            source,
            session_cache=session_cache,
            hook_registry=hook_registry,
        ),
    )


def register_model_tool(
    registry: ToolRegistry,
    source: ModelSourceSpec,
    *,
    session_cache: ModelSessionCache | None = None,
    hook_registry: ModelHookRegistry | None = None,
) -> ToolSpec:
    spec = compile_model_tool(
        source,
        session_cache=session_cache,
        hook_registry=hook_registry,
    )
    registry.register(spec)
    return spec


__all__ = ["build_model_input_schema", "compile_model_tool", "register_model_tool"]
