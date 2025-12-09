import pytest

from tests.fixtures.async_tools import async_registry, async_state_manager
from toolanything.core.tool_manager import ToolManager


@pytest.mark.asyncio
async def test_execute_tool_async_handles_coroutine_tool():
    result = await async_registry.execute_tool_async(
        "async.echo", arguments={"message": "hello"}
    )
    assert result == "hello"


@pytest.mark.asyncio
async def test_execute_tool_async_runs_sync_in_thread():
    result = await async_registry.execute_tool_async(
        "sync.identity", arguments={"value": "thread"}
    )
    assert result == "thread"


@pytest.mark.asyncio
async def test_execute_tool_async_supports_pipeline_and_state():
    result = await async_registry.execute_tool_async(
        "async.pipeline", arguments={"value": 10}, user_id="u-1", state_manager=async_state_manager
    )
    assert result == 20
    assert async_state_manager.get("u-1")["last"] == 10


@pytest.mark.asyncio
async def test_tool_manager_invoke_exposes_async_only():
    manager = ToolManager(registry=async_registry)
    output = await manager.invoke("sync.identity", {"value": "managed"})
    assert output == "managed"
