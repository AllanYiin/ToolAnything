from toolanything import ToolRegistry, tool


def test_execute_tool_does_not_retry_failures():
    registry = ToolRegistry()
    attempts = {"count": 0}

    @tool(name="demo.fail_once", description="always fails", registry=registry)
    def fail_once() -> None:
        attempts["count"] += 1
        raise RuntimeError("boom")

    try:
        registry.execute_tool("demo.fail_once")
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected RuntimeError")

    assert attempts["count"] == 1
