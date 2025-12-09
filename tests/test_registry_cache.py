from toolanything.core.models import PipelineDefinition, ToolSpec
from toolanything.core.registry import ToolRegistry


def sample_tool():
    return "tool"


def sample_pipeline():
    return "pipeline"


def test_registry_lookup_cache_and_invalidation():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="demo.tool",
            description="Demo tool",
            func=sample_tool,
            parameters={},
        )
    )

    first_lookup = registry.get("demo.tool")
    second_lookup = registry.get("demo.tool")

    assert first_lookup is sample_tool
    assert second_lookup is sample_tool
    assert registry._lookup_cache["demo.tool"] is sample_tool

    registry.register_pipeline(
        PipelineDefinition(
            name="demo.pipeline",
            description="Demo pipeline",
            func=sample_pipeline,
            parameters={},
            stateful=False,
        )
    )

    assert registry._lookup_cache == {}
    assert registry.get("demo.tool") is sample_tool
    assert registry.get("demo.pipeline") is sample_pipeline

