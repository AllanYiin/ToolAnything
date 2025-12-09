from toolanything import ToolRegistry
from toolanything import ToolRegistry
from toolanything.pipeline import PipelineContext
from toolanything.decorators import pipeline, tool


def test_tool_registration_and_metadata():
    registry = ToolRegistry()

    @tool(name="demo.echo", description="echo", registry=registry)
    def echo(text: str) -> dict:
        return {"echo": text}

    registered = registry.get_tool("demo.echo")
    assert registered.description == "echo"
    assert "text" in registered.parameters["properties"]
    assert registered.func("hi") == {"echo": "hi"}
    assert echo.tool_spec.name == "demo.echo"


def test_global_registry_auto_registration():
    ToolRegistry._global_instance = None  # type: ignore[attr-defined]

    @tool(name="demo.auto", description="auto")
    def auto(text: str) -> dict:
        return {"auto": text}

    registry = ToolRegistry.global_instance()
    registered = registry.get_tool("demo.auto")
    assert registered.description == "auto"
    assert registered.func("ping") == {"auto": "ping"}
    ToolRegistry._global_instance = None  # type: ignore[attr-defined]


def test_pipeline_auto_registration():
    ToolRegistry._global_instance = None  # type: ignore[attr-defined]

    @pipeline(name="demo.pipeline", description="pipeline")
    def sample(ctx, text: str):
        ctx.set("value", text)
        return {"echo": text}

    registry = ToolRegistry.global_instance()
    registered = registry.get_pipeline("demo.pipeline")
    assert registered.description == "pipeline"
    assert "text" in registered.parameters["properties"]
    assert registered.func(PipelineContext(None, None), text="hello") == {"echo": "hello"}
    ToolRegistry._global_instance = None  # type: ignore[attr-defined]
