import json

from tests.fixtures.sample_tools import registry
from toolanything.openai_runtime import OpenAIChatRuntime


def test_openai_chat_runtime_executes_tool_call_payload():
    runtime = OpenAIChatRuntime(registry)

    tool_call = runtime.create_tool_call(
        "math.add",
        {"a": 2, "b": 5},
        tool_call_id="call_123",
    )
    invocation = runtime.execute_tool_call(tool_call)

    assert tool_call["id"] == "call_123"
    assert tool_call["function"]["name"] == "math_add"
    assert invocation["role"] == "tool"
    assert invocation["tool_call_id"] == "call_123"
    assert invocation["name"] == "math.add"
    assert invocation["content"] == "7"


def test_openai_chat_runtime_runs_mocked_tool_loop():
    runtime = OpenAIChatRuntime(registry)
    replies = [
        {
            "content": None,
            "tool_calls": [
                runtime.create_tool_call(
                    "math.add",
                    {"a": 3, "b": 4},
                    tool_call_id="call_math_add",
                )
            ],
        },
        {"content": "完成", "tool_calls": []},
    ]

    def fake_requester(**kwargs):
        assert kwargs["tools"]
        return replies.pop(0)

    result = runtime.run(
        api_key="sk-test",
        model="gpt-test",
        prompt="請呼叫 math.add",
        requester=fake_requester,
    )

    assert result["final_text"] == "完成"
    assistant_entry = next(entry for entry in result["transcript"] if entry["role"] == "assistant")
    assert assistant_entry["tool_calls"][0]["function"]["name"] == "math.add"
    tool_entry = next(entry for entry in result["transcript"] if entry["role"] == "tool")
    assert tool_entry["name"] == "math.add"
    assert json.loads(tool_entry["content"]) == 7
