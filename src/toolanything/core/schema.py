"""Schema 生成工具，根據函數 type hints 產生 JSON Schema。"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Dict, get_args, get_origin


@dataclass
class ParameterSpec:
    name: str
    schema: Dict[str, Any]
    required: bool


_TYPE_MAPPING = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
}


def _literal_schema(py_type: Any) -> Dict[str, Any]:
    values = list(get_args(py_type))
    return {"enum": values}


def _container_schema(origin: Any, args: tuple[Any, ...]) -> Dict[str, Any]:
    if origin in (list, tuple):
        item_type = args[0] if args else Any
        return {"type": "array", "items": python_type_to_schema(item_type)}
    if origin in (dict, Dict):
        value_type = args[1] if len(args) > 1 else Any
        return {
            "type": "object",
            "additionalProperties": python_type_to_schema(value_type),
        }
    return {"type": "string"}


def python_type_to_schema(py_type: Any) -> Dict[str, Any]:
    """將 Python 類型轉換成 JSON Schema 片段。"""
    if py_type in _TYPE_MAPPING:
        return dict(_TYPE_MAPPING[py_type])

    origin = get_origin(py_type)
    args = get_args(py_type)

    if origin is None:
        return {"type": "string"}

    if origin is inspect._empty:  # pragma: no cover - 兼容 inspect 特殊值
        return {"type": "string"}

    if origin is type(None):  # pragma: no cover
        return {"type": "null"}

    if str(origin).endswith("Literal"):
        return _literal_schema(py_type)

    return _container_schema(origin, args)


def build_parameters_schema(func: Any) -> Dict[str, Any]:
    """從函數簽名生成 OpenAI/MCP 相容的 parameters schema。"""
    signature = inspect.signature(func)
    properties: Dict[str, Any] = {}
    required = []

    for name, param in signature.parameters.items():
        if name == "ctx":
            continue

        annotation = param.annotation if param.annotation is not inspect._empty else str
        schema = python_type_to_schema(annotation)
        if param.default is not inspect._empty:
            schema = {**schema, "default": param.default}
            is_required = False
        else:
            is_required = True

        properties[name] = schema
        if is_required:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
