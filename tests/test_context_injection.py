from toolanything.core.models import ToolSpec
from toolanything.core.registry import ToolRegistry
from toolanything.pipeline import PipelineContext
from toolanything.core.schema import build_parameters_schema
from toolanything.state.manager import StateManager


def _tool_with_context(context: PipelineContext, text: str) -> str:
    context.set("last_text", text)
    return context.get("last_text")


def test_schema_skips_context_parameter_with_type():
    schema = build_parameters_schema(_tool_with_context)

    assert "context" not in schema["properties"]
    assert schema["required"] == ["text"]


def test_registry_auto_injects_context_for_tools():
    registry = ToolRegistry()
    registry.register(
        ToolSpec.from_function(
            _tool_with_context,
            name="with_context",
            description="tool needing pipeline context",
        )
    )

    manager = StateManager()
    result = registry.execute_tool(
        "with_context", arguments={"text": "hello"}, user_id="u42", state_manager=manager
    )

    assert result == "hello"
    assert manager.get("u42")["last_text"] == "hello"
