import inspect

from toolanything.core.schema import build_parameters_schema, python_type_to_schema


def sample(a: int, b: str, c: float = 1.0):
    return a, b, c


def test_python_type_to_schema_basic():
    assert python_type_to_schema(int) == {"type": "integer"}
    assert python_type_to_schema(str) == {"type": "string"}
    assert python_type_to_schema(list) == {"type": "array"}


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
