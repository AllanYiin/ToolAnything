from __future__ import annotations

from inspect import signature
from typing import Any, get_origin, get_args

from .tool_definition import ToolArgument


def _python_type_to_json_schema(py_type: Any) -> dict:
    origin = get_origin(py_type)
    args = get_args(py_type)
    if origin is None:
        mapping = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
            dict: {"type": "object"},
            list: {"type": "array"},
        }
        return mapping.get(py_type, {"type": "string"})
    if origin is list or origin is tuple:
        return {"type": "array", "items": _python_type_to_json_schema(args[0] if args else Any)}
    if origin is dict:
        return {
            "type": "object",
            "additionalProperties": _python_type_to_json_schema(args[1] if len(args) > 1 else Any),
        }
    if origin is None and isinstance(py_type, type):
        return {"type": "string"}
    return {"type": "string"}


def build_input_schema(fn) -> tuple[list[ToolArgument], dict]:
    sig = signature(fn)
    properties = {}
    required = []
    args: list[ToolArgument] = []
    for name, param in sig.parameters.items():
        annotation = param.annotation if param.annotation is not param.empty else Any
        schema = _python_type_to_json_schema(annotation)
        properties[name] = schema
        is_required = param.default is param.empty
        if is_required:
            required.append(name)
        args.append(
            ToolArgument(
                name=name,
                type=annotation,
                required=is_required,
                default=None if param.default is param.empty else param.default,
                description=param.__doc__ if hasattr(param, "__doc__") else None,
            )
        )
    json_schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        json_schema["required"] = required
    return args, json_schema


def build_output_schema(return_type: Any) -> dict | None:
    if return_type is None:
        return None
    return _python_type_to_json_schema(return_type)
