from toolanything import ToolRegistry
from toolanything.decorators import tool


def test_tool_registration_and_metadata():
    registry = ToolRegistry()

    @tool(path="demo.echo", description="echo", registry=registry)
    def echo(text: str) -> dict:
        return {"echo": text}

    registered = registry.get_tool("demo.echo")
    assert registered.description == "echo"
    assert "text" in registered.parameters["properties"]
    assert registered.func("hi") == {"echo": "hi"}
    assert echo.metadata.path == "demo.echo"
