import pytest

from tests.fixtures.async_tools import async_registry
from tests.fixtures.sample_tools import registry
from toolanything.adapters.openai_adapter import OpenAIAdapter, export_tools


def test_export_tools_schema():
    tools = export_tools(registry)
    assert any(tool["function"]["name"] == "math.add" for tool in tools)
    add_tool = next(t for t in tools if t["function"]["name"] == "math.add")
    assert add_tool["function"]["parameters"]["properties"]["b"]["default"] == 1


def test_openai_function_call_payload():
    adapter = OpenAIAdapter(registry)
    payload = adapter.to_function_call("math.add", {"a": 3})

    assert payload == {
        "type": "function",
        "function": {
            "name": "math.add",
            "arguments": "{\"a\": 3}",
        },
    }


@pytest.mark.asyncio
async def test_openai_adapter_invocation_from_json_arguments():
    adapter = OpenAIAdapter(registry)
    invocation = await adapter.to_invocation(
        "math.add", "{\"a\": 2, \"b\": 5}", tool_call_id="call_123"
    )

    assert invocation["role"] == "tool"
    assert invocation["tool_call_id"] == "call_123"
    assert invocation["name"] == "math.add"
    assert invocation["arguments"] == {"a": 2, "b": 5}
    assert invocation["content"] == "7"
    assert invocation["result"] == {"type": "text", "content": "7"}
    assert invocation["raw_result"] == 7


@pytest.mark.asyncio
async def test_openai_adapter_invocation_supports_async_tool():
    adapter = OpenAIAdapter(async_registry)
    invocation = await adapter.to_invocation("async.echo", {"message": "pong"})

    assert invocation["name"] == "async.echo"
    assert invocation["content"] == "pong"
    assert invocation["result"] == {"type": "text", "content": "pong"}
    assert invocation["raw_result"] == "pong"
