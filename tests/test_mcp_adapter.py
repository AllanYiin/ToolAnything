from tests.fixtures.sample_tools import registry
from toolanything.adapters.mcp_adapter import export_tools


def test_export_mcp_tools():
    tools = export_tools(registry)
    assert any(t["name"] == "math.add" for t in tools)
    schema = next(t for t in tools if t["name"] == "math.add")
    assert "properties" in schema["input_schema"]
