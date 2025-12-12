import inspect

from toolanything.core import schema
from toolanything.core.schema import build_parameters_schema, python_type_to_schema


def sample(a: int, b: str, c: float = 1.0):
    return a, b, c


def test_python_type_to_schema_basic():
    assert python_type_to_schema(int) == {"type": "integer"}
    assert python_type_to_schema(str) == {"type": "string"}
    assert python_type_to_schema(list) == {"type": "array"}


def test_python_type_to_schema_complex_types():
    from typing import Dict, List, Literal, Optional, Union
    from enum import Enum

    assert python_type_to_schema(bool) == {"type": "boolean"}
    assert python_type_to_schema(float) == {"type": "number"}

    union_schema = python_type_to_schema(Union[int, str])
    assert union_schema == {
        "oneOf": [
            {"type": "integer"},
            {"type": "string"},
        ]
    }

    optional_schema = python_type_to_schema(Optional[int])
    assert optional_schema == {
        "oneOf": [
            {"type": "integer"},
            {"type": "null"},
        ]
    }

    nested_list_schema = python_type_to_schema(List[List[int]])
    assert nested_list_schema == {
        "type": "array",
        "items": {"type": "array", "items": {"type": "integer"}},
    }

    nested_dict_schema = python_type_to_schema(Dict[str, List[int]])
    assert nested_dict_schema == {
        "type": "object",
        "additionalProperties": {
            "type": "array",
            "items": {"type": "integer"},
        },
    }

    literal_schema = python_type_to_schema(Literal["red", "blue"])
    assert literal_schema == {"enum": ["red", "blue"]}

    class Status(Enum):
        READY = "ready"
        DONE = "done"

    enum_schema = python_type_to_schema(Status)
    assert enum_schema == {"type": "string", "enum": ["ready", "done"]}


def test_python_type_to_schema_cache_and_copy():
    schema._python_type_to_schema_cached.cache_clear()

    first = python_type_to_schema(int)
    cache_stats_after_first = schema._python_type_to_schema_cached.cache_info()
    assert cache_stats_after_first.misses == 1

    first["patched"] = True

    second = python_type_to_schema(int)
    cache_stats_after_second = schema._python_type_to_schema_cached.cache_info()
    assert cache_stats_after_second.hits >= 1
    assert "patched" not in second


def test_build_parameters_schema():
    schema = build_parameters_schema(sample)
    assert schema["type"] == "object"
    assert "a" in schema["properties"]
    assert "b" in schema["properties"]
    assert "c" in schema["properties"]
    assert "a" in schema["required"]
    assert "b" in schema["required"]
    assert "c" not in schema["required"]
    assert schema["properties"]["c"]["default"] == 1.0


def test_build_parameters_schema_skips_self_and_cls():
    class Demo:
        def instance_method(self, value: int, flag: bool):
            return value if flag else 0

        @classmethod
        def class_method(cls, text: str):
            return text

    instance_schema = build_parameters_schema(Demo.instance_method)
    assert set(instance_schema["properties"].keys()) == {"value", "flag"}

    class_schema = build_parameters_schema(Demo.class_method.__func__)
    assert set(class_schema["properties"].keys()) == {"text"}
