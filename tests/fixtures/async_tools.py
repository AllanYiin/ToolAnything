"""非同步工具與 Pipeline 示範。"""
import asyncio

from toolanything import ToolRegistry, pipeline, tool
from toolanything.state import StateManager

async_registry = ToolRegistry()
async_state_manager = StateManager()


@tool(name="async.echo", description="回傳輸入內容", registry=async_registry)
async def async_echo(message: str) -> str:
    await asyncio.sleep(0)
    return message


@tool(name="sync.identity", description="同步回傳輸入", registry=async_registry)
def sync_identity(value: str) -> str:
    return value


@pipeline(
    name="async.pipeline",
    description="示範 async pipeline 呼叫",
    registry=async_registry,
    state_manager=async_state_manager,
)
async def async_pipeline(ctx, value: int):
    await asyncio.sleep(0)
    ctx.set("last", value)
    return value * 2
