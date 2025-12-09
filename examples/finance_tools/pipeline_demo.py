"""Finance pipeline 範例，示範 pipeline decorator 與狀態管理。"""
from toolanything import StateManager, ToolRegistry, pipeline, tool

registry = ToolRegistry()
state_manager = StateManager()


@tool(name="finance.rate", description="回傳匯率", registry=registry)
def get_rate(pair: str) -> dict:
    return {"pair": pair, "rate": 32.5}


@pipeline(
    name="finance.convert",
    description="轉換金額並記錄最近一次轉換",
    registry=registry,
    state_manager=state_manager,
)
def convert(ctx, amount: float, pair: str):
    rate = get_rate(pair)
    ctx.set("last_pair", pair)
    return {"amount": amount * rate["rate"], "pair": pair}


def main():
    result = convert(amount=100, pair="USD/TWD", user_id="demo")
    print(result)
    print(state_manager.get("demo"))


if __name__ == "__main__":
    main()
