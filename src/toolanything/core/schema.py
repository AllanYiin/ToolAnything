"""Schema 生成工具，根據函數 type hints 產生 JSON Schema。"""
from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from types import UnionType
from typing import Any, Dict, get_args, get_origin

from toolanything.pipeline.context import is_context_parameter


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


def _enum_schema(py_type: type[Enum]) -> Dict[str, Any]:
    values = [member.value for member in py_type]
    schema: Dict[str, Any] = {"enum": values}

    if values and type(values[0]) in _TYPE_MAPPING:
        schema = {"type": _TYPE_MAPPING[type(values[0])]["type"], **schema}

    return schema


def _union_schema(args: tuple[Any, ...]) -> Dict[str, Any]:
    return {"oneOf": [python_type_to_schema(arg) for arg in args]}


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


@lru_cache(maxsize=128)
def _python_type_to_schema_cached(py_type: Any) -> Dict[str, Any]:
    """快取版本的類型轉換，避免重複計算。"""
    if py_type in _TYPE_MAPPING:
        return dict(_TYPE_MAPPING[py_type])

    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return _enum_schema(py_type)

    if py_type is type(None):  # pragma: no cover
        return {"type": "null"}

    origin = get_origin(py_type)
    args = get_args(py_type)

    if origin is None:
        return {"type": "string"}

    if origin is inspect._empty:  # pragma: no cover - 兼容 inspect 特殊值
        return {"type": "string"}

    if str(origin).endswith("Literal"):
        return _literal_schema(py_type)

    if origin in (inspect._empty, None):  # pragma: no cover
        return {"type": "string"}

    if origin in (getattr(__import__("typing"), "Union", None), UnionType):
        return _union_schema(args)

    return _container_schema(origin, args)


def python_type_to_schema(py_type: Any) -> Dict[str, Any]:
    """將 Python 類型轉換成 JSON Schema 片段並確保回傳可安全修改的副本。"""

    # 深拷貝避免外部修改破壞快取內容
    return copy.deepcopy(_python_type_to_schema_cached(py_type))


def build_parameters_schema(func: Any) -> Dict[str, Any]:
    """從函數簽名生成 OpenAI/MCP 相容的 parameters schema。"""
    signature = inspect.signature(func)
    properties: Dict[str, Any] = {}
    required = []

    for name, param in signature.parameters.items():
        if name in {"self", "cls"}:
            continue

        if is_context_parameter(param):
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
