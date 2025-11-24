# ToolAnything

ToolAnything 是一個「跨協議 AI 工具中介層」，開發者只需撰寫一次函數即可同時被 OpenAI Tool Calling 與 MCP 使用。專案核心特色包含：

- 單一函數、雙協議兼容：使用 `@tool` decorator 註冊後即可直接輸出 OpenAI/MCP schema。
- 語法糖簡潔：依據 type hints 生成 JSON Schema，降低心智負擔。
- 支援 pipeline 與多使用者 state：透過 `@pipeline` decorator 組裝跨工具流程並維持使用者上下文。

## 快速範例

```python
from toolanything import tool, pipeline, ToolRegistry, StateManager

registry = ToolRegistry()
state_manager = StateManager()

@tool(path="weather.query", description="取得城市天氣", registry=registry)
def get_weather(city: str, unit: str = "c") -> dict:
    return {"city": city, "unit": unit, "temp": 25}

@pipeline(name="trip.plan", description="簡易行程規劃", registry=registry)
def trip_plan(ctx, city: str):
    weather = registry.get("weather.query")
    ctx.set("latest_city", city)
    return weather(city=city)
```

## 目錄結構

- `src/toolanything/core/`：核心資料模型與 Schema 生成邏輯。
- `src/toolanything/decorators/`：`@tool` 與 `@pipeline` 語法糖。
- `src/toolanything/adapters/`：OpenAI/MCP 協議轉換。
- `src/toolanything/state/`：多使用者 session 管理。
- `src/toolanything/pipeline/`：流程執行輔助。
- `src/toolanything/utils/`：共用工具函數。

## 下一步

- 撰寫更多自動化測試涵蓋 decorator 與 adapter。
- 擴充 CLI、文件與 examples 目錄。
- 引入 SecurityManager、ResultSerializer 等擴展點的實際應用範例。
