from tests.fixtures.sample_tools import registry
from toolanything.adapters.openai_adapter import OpenAIAdapter, export_tools


def test_export_tools_schema():
    tools = export_tools(registry)
    assert any(tool["function"]["name"] == "math.add" for tool in tools)
    add_tool = next(t for t in tools if t["function"]["name"] == "math.add")
    assert add_tool["function"]["parameters"]["properties"]["b"]["default"] == 1


def test_openai_adapter_invocation():
    adapter = OpenAIAdapter(registry)
    invocation = adapter.to_invocation("math.add", {"a": 2, "b": 5})

    assert invocation["type"] == "function"
    assert invocation["name"] == "math.add"
    assert invocation["arguments"] == {"a": 2, "b": 5}
    assert invocation["result"] == 7
