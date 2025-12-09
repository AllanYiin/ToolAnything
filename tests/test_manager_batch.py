import pytest

from toolanything.core.tool_manager import ToolManager


@pytest.mark.asyncio
async def test_invoke_many_basic():
    manager = ToolManager()

    @manager.register(name="add", description="add numbers")
    def add(a: int, b: int) -> int:
        return a + b

    args_list = [{"a": 1, "b": 2}, {"a": 10, "b": 5}]
    out = await manager.invoke_many("add", args_list, concurrency=2)
    assert out == [3, 15]


@pytest.mark.asyncio
async def test_invoke_many_retry():
    manager = ToolManager()
    state = {"count": 0}

    @manager.register(name="unstable", description="unstable")
    def unstable(x: int) -> int:
        state["count"] += 1
        if state["count"] < 2:
            raise ValueError("fail once")
        return x

    out = await manager.invoke_many(
        "unstable",
        [{"x": 1}],
        max_retries=2,
        concurrency=1,
    )
    assert out == [1]
