from toolanything import tool
from toolanything.core.metadata import ToolMetadata, normalize_metadata
from toolanything.core.models import ToolSpec
from toolanything.core.registry import ToolRegistry


def test_metadata_normalization_defaults():
    metadata = normalize_metadata({"cost": "1.5", "unknown": "keep"}, tags=["alpha"])
    assert metadata == ToolMetadata(
        cost=1.5,
        latency_hint_ms=None,
        side_effect=None,
        category=None,
        tags=("alpha",),
        extra={"unknown": "keep"},
    )


def test_metadata_default_values_when_missing():
    metadata = normalize_metadata({}, tags=None)
    assert metadata.cost is None
    assert metadata.latency_hint_ms is None
    assert metadata.side_effect is None
    assert metadata.category is None
    assert metadata.tags == ()
    assert metadata.extra == {}


def test_decorator_register_metadata_roundtrip():
    registry = ToolRegistry()

    @tool(
        name="demo.echo",
        description="回聲",
        metadata={
            "cost": 3.0,
            "latency_hint_ms": 10,
            "side_effect": False,
            "category": "io",
            "tags": ["cli"],
            "extra": "value",
        },
        registry=registry,
    )
    def echo(message: str) -> str:
        return message

    spec = registry.get_tool("demo.echo")
    normalized = spec.normalized_metadata()
    assert normalized.cost == 3.0
    assert normalized.latency_hint_ms == 10
    assert normalized.side_effect is False
    assert normalized.category == "io"
    assert "cli" in normalized.tags
    assert normalized.extra["extra"] == "value"
    assert spec.tool_metadata == normalized
