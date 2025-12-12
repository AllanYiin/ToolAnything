"""驗證 PipelineContext 能夠注入到一般工具。"""

from toolanything import ToolRegistry, tool
from toolanything.pipeline import PipelineContext
from toolanything.state import StateManager


def test_tool_receives_context_and_updates_state():
    registry = ToolRegistry()
    state_manager = StateManager()

    @tool(name="demo.contextual", description="stateful tool", registry=registry)
    def contextual_tool(ctx: PipelineContext, message: str) -> str:
        ctx.set("message", message)
        return ctx.get("message")

    spec = registry.get_tool("demo.contextual")
    assert "ctx" not in spec.parameters["properties"]

    result = registry.execute_tool(
        "demo.contextual",
        arguments={"message": "hello"},
        user_id="user-1",
        state_manager=state_manager,
    )

    assert result == "hello"
    assert state_manager.get("user-1")["message"] == "hello"


def test_context_annotation_allows_custom_parameter_name():
    registry = ToolRegistry()
    state_manager = StateManager()

    @tool(name="demo.alias", description="alias ctx", registry=registry)
    def contextual_alias(context: PipelineContext, value: int) -> int:
        context.set("alias", value)
        return context.get("alias")

    spec = registry.get_tool("demo.alias")
    assert "context" not in spec.parameters["properties"]

    result = registry.execute_tool(
        "demo.alias",
        arguments={"value": 99},
        user_id="user-2",
        state_manager=state_manager,
    )

    assert result == 99
    assert state_manager.get("user-2")["alias"] == 99
