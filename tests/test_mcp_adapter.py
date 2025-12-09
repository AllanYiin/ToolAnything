from tests.fixtures.sample_tools import registry
from toolanything.adapters.mcp_adapter import MCPAdapter, export_tools


def test_export_mcp_tools():
    tools = export_tools(registry)
    assert any(t["name"] == "math.add" for t in tools)
    schema = next(t for t in tools if t["name"] == "math.add")
    assert "properties" in schema["input_schema"]


def test_mcp_adapter_invocation():
    adapter = MCPAdapter(registry)
    invocation = adapter.to_invocation("math.add", {"a": 3})

    assert invocation["name"] == "math.add"
    assert invocation["arguments"] == {"a": 3}
    assert invocation["result"] == 4
