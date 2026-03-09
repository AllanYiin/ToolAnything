from __future__ import annotations

import pytest

from toolanything.core.invokers import CallableInvoker
from toolanything.core.models import ToolContract, ToolSpec
from toolanything.core.runtime_types import ExecutionContext, InvocationResult
from toolanything.pipeline import PipelineContext
from toolanything.state import StateManager


def _sync_identity(value: str) -> str:
    return value


async def _async_identity(value: str) -> str:
    return value


def _context_echo(context: PipelineContext, text: str) -> str:
    context.set("echo", text)
    return context.get("echo")


class DummyInvoker:
    async def invoke(
        self,
        input,
        context: ExecutionContext,
        stream=None,
        *,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> InvocationResult:
        del stream, inject_context, context_arg
        return InvocationResult(
            output={
                "tool_name": context.tool_name,
                "user_id": context.user_id,
                "arguments": dict(input or {}),
            }
        )


@pytest.mark.asyncio
async def test_callable_invoker_runs_sync_function():
    invoker = CallableInvoker(_sync_identity)
    result = await invoker.invoke({"value": "sync"}, ExecutionContext(tool_name="sync.identity"))

    assert result == InvocationResult(output="sync")


@pytest.mark.asyncio
async def test_callable_invoker_runs_async_function():
    invoker = CallableInvoker(_async_identity)
    result = await invoker.invoke({"value": "async"}, ExecutionContext(tool_name="async.identity"))

    assert result == InvocationResult(output="async")


@pytest.mark.asyncio
async def test_callable_invoker_auto_injects_pipeline_context():
    state_manager = StateManager()
    invoker = CallableInvoker(_context_echo)

    result = await invoker.invoke(
        {"text": "hello"},
        ExecutionContext(
            tool_name="context.echo",
            user_id="user-1",
            state_manager=state_manager,
        ),
    )

    assert result == InvocationResult(output="hello")
    assert state_manager.get("user-1")["echo"] == "hello"


def test_tool_spec_from_function_builds_contract_and_callable_invoker():
    spec = ToolSpec.from_function(
        _sync_identity,
        name="demo.identity",
        description="回傳輸入值",
        tags=["demo"],
    )

    assert isinstance(spec.invoker, CallableInvoker)
    assert spec.func is _sync_identity
    assert spec.contract == ToolContract(
        name="demo.identity",
        description="回傳輸入值",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        adapters=None,
        tags=("demo",),
        strict=True,
        metadata={},
        documentation=spec.documentation,
        source_type="callable",
        invoker_id="demo.identity",
    )


@pytest.mark.asyncio
async def test_tool_spec_can_be_invoker_first_without_callable():
    spec = ToolSpec(
        name="demo.virtual",
        description="不需要 Python function 的工具契約",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        source_type="custom",
        invoker_id="demo.virtual",
        invoker=DummyInvoker(),
    )

    assert spec.func is None
    assert spec.contract.source_type == "custom"

    result = await spec.invoker.invoke({}, ExecutionContext(tool_name=spec.name, user_id="u-1"))
    assert result == InvocationResult(
        output={"tool_name": "demo.virtual", "user_id": "u-1", "arguments": {}}
    )
