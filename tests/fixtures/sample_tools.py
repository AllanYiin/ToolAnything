"""測試用示範工具。"""
from toolanything import ToolRegistry, pipeline, tool
from toolanything.state import StateManager

registry = ToolRegistry()
state_manager = StateManager()


@tool(name="math.add", description="兩數相加", registry=registry)
def add(a: int, b: int = 1) -> int:
    return a + b


@pipeline(
    name="math.workflow",
    description="示範 pipeline 串接",
    registry=registry,
    state_manager=state_manager,
)
def workflow(ctx, a: int, b: int):
    ctx.set("last_sum", a + b)
    return {"sum": add(a, b)}
