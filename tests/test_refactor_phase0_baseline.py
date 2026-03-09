from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures.async_tools import async_registry
from tests.fixtures.sample_tools import registry as sample_registry
from toolanything import ToolRegistry, tool
from toolanything.adapters.mcp_adapter import MCPAdapter
from toolanything.core.tool_manager import ToolManager
from toolanything.exceptions import ToolError
from toolanything.pipeline import PipelineContext
from toolanything.state import StateManager


GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_golden(*parts: str):
    path = GOLDEN_DIR.joinpath(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_phase0_tool_decorator_registration_and_execution_baseline():
    registry = ToolRegistry()

    @tool(name="phase0.echo", description="回傳輸入內容", registry=registry)
    def echo(text: str) -> dict[str, str]:
        return {"echo": text}

    spec = registry.get_tool("phase0.echo")

    assert spec.name == "phase0.echo"
    assert echo.tool_spec == spec
    assert spec.func("baseline") == {"echo": "baseline"}
    assert spec.parameters["properties"]["text"] == {"type": "string"}
    assert await registry.execute_tool_async("phase0.echo", arguments={"text": "baseline"}) == {
        "echo": "baseline"
    }


@pytest.mark.asyncio
async def test_phase0_tool_manager_invoke_baseline_for_sync_and_async_functions():
    registry = ToolRegistry()
    manager = ToolManager(registry=registry)

    @manager.register(name="phase0.sync_identity", description="同步回傳")
    def sync_identity(value: str) -> str:
        return value

    @manager.register(name="phase0.async_identity", description="非同步回傳")
    async def async_identity(value: str) -> str:
        return value

    assert await manager.invoke("phase0.sync_identity", {"value": "sync"}) == "sync"
    assert await manager.invoke("phase0.async_identity", {"value": "async"}) == "async"


@pytest.mark.asyncio
async def test_phase0_execute_tool_async_context_injection_baseline():
    registry = ToolRegistry()
    state_manager = StateManager()

    @tool(name="phase0.context_echo", description="讀寫 context", registry=registry)
    def context_echo(context: PipelineContext, text: str) -> dict[str, str | None]:
        context.set("remembered", text)
        return {"remembered": context.get("remembered"), "user_id": context.user_id}

    result = await registry.execute_tool_async(
        "phase0.context_echo",
        arguments={"text": "hello"},
        user_id="user-phase0",
        state_manager=state_manager,
    )

    assert result == {"remembered": "hello", "user_id": "user-phase0"}
    assert state_manager.get("user-phase0")["remembered"] == "hello"


def test_phase0_openai_schema_matches_golden_snapshot():
    assert sample_registry.to_openai_tools() == _load_golden("openai_tools", "sample_registry.json")


def test_phase0_mcp_schema_matches_golden_snapshot():
    assert sample_registry.to_mcp_tools() == _load_golden("mcp_tools", "sample_registry.json")


@pytest.mark.asyncio
async def test_phase0_mcp_adapter_to_invocation_success_baseline():
    adapter = MCPAdapter(sample_registry)

    invocation = await adapter.to_invocation("math.add", {"a": 6})

    assert invocation == {
        "name": "math.add",
        "arguments": {"a": 6},
        "result": {"contentType": "text/plain", "content": "7"},
        "raw_result": 7,
        "audit": {
            "tool": "math.add",
            "user": "anonymous",
            "args": {"a": 6},
        },
    }


@pytest.mark.asyncio
async def test_phase0_mcp_adapter_to_invocation_structured_error_baseline():
    registry = ToolRegistry()

    @tool(name="phase0.known_error", description="已知錯誤", registry=registry)
    def known_error() -> None:
        raise ToolError("boom", error_type="tool_failed", data={"reason": "baseline"})

    adapter = MCPAdapter(registry)
    invocation = await adapter.to_invocation("phase0.known_error")

    assert invocation == {
        "name": "phase0.known_error",
        "arguments": {},
        "error": {
            "type": "tool_failed",
            "message": "boom",
            "data": {"reason": "baseline"},
        },
        "audit": {"tool": "phase0.known_error", "user": "anonymous", "args": {}},
    }


@pytest.mark.asyncio
async def test_phase0_mcp_adapter_to_invocation_internal_error_baseline():
    registry = ToolRegistry()

    @tool(name="phase0.unexpected_error", description="未預期錯誤", registry=registry)
    def unexpected_error() -> None:
        raise RuntimeError("boom")

    adapter = MCPAdapter(registry)
    invocation = await adapter.to_invocation("phase0.unexpected_error")

    assert invocation == {
        "name": "phase0.unexpected_error",
        "arguments": {},
        "error": {"type": "internal_error", "message": "工具執行時發生未預期錯誤"},
        "audit": {"tool": "phase0.unexpected_error", "user": "anonymous", "args": {}},
    }


def test_phase0_async_registry_schema_matches_existing_behavior():
    assert async_registry.to_mcp_tools() == [
        {
            "name": "async.echo",
            "description": "回傳輸入內容",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
        },
        {
            "name": "sync.identity",
            "description": "同步回傳輸入",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
        },
        {
            "name": "async.pipeline",
            "description": "示範 async pipeline 呼叫",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "additionalProperties": False,
            },
        },
    ]
