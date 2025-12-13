import pytest

from toolanything import ToolRegistry, pipeline, tool
from toolanything.pipeline import PipelineContext
from toolanything.state.manager import StateManager


def test_type_prefix_lookup_and_registration():
    registry = ToolRegistry()

    @tool(name="tool:echo", description="echo", registry=registry)
    def echo(context: PipelineContext, text: str) -> dict:
        context.set("echo", text)
        return {"echo": text, "user": context.user_id}

    @pipeline(name="pipeline:transform", description="pipeline", registry=registry)
    def transform(ctx: PipelineContext, text: str) -> dict:
        return {"text": text, "user": ctx.user_id}

    tool_spec = registry.get_tool("tool:echo")
    pipeline_spec = registry.get_pipeline("pipeline:transform")

    assert tool_spec.name == "tool:echo"
    assert pipeline_spec.name == "pipeline:transform"

    state = StateManager()
    result = registry.execute_tool(
        "tool:echo",
        arguments={"text": "hello"},
        user_id="u1",
        state_manager=state,
        inject_context=True,
    )

    assert result == {"echo": "hello", "user": "u1"}
    assert state.get("u1")["echo"] == "hello"
    assert registry.get("pipeline:transform") is pipeline_spec.func


def test_duplicate_name_between_tool_and_pipeline_is_rejected():
    registry = ToolRegistry()

    @pipeline(name="shared", description="pipeline", registry=registry)
    def shared(ctx: PipelineContext) -> dict:
        return {}

    with pytest.raises(ValueError):
        @tool(name="shared", description="tool", registry=registry)
        def duplicated() -> dict:
            return {}


def test_plain_lookup_errors_when_names_clash():
    registry = ToolRegistry()

    @tool(name="alpha", description="tool", registry=registry)
    def alpha_tool() -> dict:
        return {}

    with pytest.raises(ValueError):
        @pipeline(name="alpha", description="pipeline", registry=registry)
        def alpha_pipeline(ctx: PipelineContext) -> dict:
            return {}

    # 確認即使使用前綴，實際查詢仍需指定正確的型別。
    assert registry.get("tool:alpha")() == {}


def test_unregister_normalizes_namespaced_names():
    registry = ToolRegistry()

    @tool(name="tool:echo", description="echo", registry=registry)
    def echo() -> dict:
        return {}

    # 先進行查詢以驗證快取機制，並確認註冊成功。
    assert registry.get("tool:echo")() == {}
    assert ("tool", "echo") in registry._lookup_cache

    registry.unregister("tool:echo")

    assert "echo" not in registry._tools
    assert registry._lookup_cache == {}
    with pytest.raises(KeyError):
        registry.get("tool:echo")
