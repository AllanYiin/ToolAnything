import pytest

from toolanything.core.tool_manager import ToolManager
from toolanything.pipeline.steps import ParallelStep, ToolStep


@pytest.mark.asyncio
async def test_parallel_step_branches():
    manager = ToolManager()

    @manager.register(name="echo", description="echo input")
    def echo(input: str) -> str:  # noqa: A002 - align with tool input naming
        return input

    @manager.register(name="upper", description="upper input")
    def upper(input: str) -> str:  # noqa: A002 - align with tool input naming
        return input.upper()

    step = ParallelStep(
        steps={
            "a": ToolStep("echo"),
            "b": ToolStep("upper"),
        },
        concurrency=2,
    )

    out = await step.run(manager, {"input": "hi"})
    assert out == {"a": "hi", "b": "HI"}
