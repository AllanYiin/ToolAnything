import pytest

from toolanything.pipeline import PipelineContext
from toolanything.state.manager import PersistentStateManager, StateManager


def test_pipeline_context_sync_state_manager():
    manager = StateManager()
    ctx = PipelineContext(manager, user_id="u1")

    ctx.set("foo", "bar")
    assert ctx.get("foo") == "bar"


def test_pipeline_context_sync_with_async_state_manager():
    manager = PersistentStateManager()
    ctx = PipelineContext(manager, user_id="u2")

    ctx.set("alpha", 123)
    assert ctx.get("alpha") == 123


@pytest.mark.asyncio
async def test_pipeline_context_async_access_with_async_state_manager():
    manager = PersistentStateManager()
    ctx = PipelineContext(manager, user_id="u3")

    await ctx.aset("beta", "value")
    assert await ctx.aget("beta") == "value"
