# ToolAnything

ToolAnything 是一個「跨協議 AI 工具中介層」，開發者只需撰寫一次函數即可同時被 OpenAI Tool Calling 與 MCP 使用。專案核心特色包含：

- 單一函數、雙協議兼容：使用 `@tool` decorator 註冊後即可直接輸出 OpenAI/MCP schema。
- 語法糖簡潔：依據 type hints 生成 JSON Schema，降低心智負擔。
- 支援 pipeline 與多使用者 state：透過 `@pipeline` decorator 組裝跨工具流程並維持使用者上下文。

## 快速範例

```python
from toolanything import tool, pipeline, ToolRegistry, StateManager

state_manager = StateManager()

# 不需額外指定 registry，會自動使用全域預設註冊表
@tool(path="weather.query", description="取得城市天氣")
def get_weather(city: str, unit: str = "c") -> dict:
    return {"city": city, "unit": unit, "temp": 25}

# Pipeline 同樣自動註冊
@pipeline(name="trip.plan", description="簡易行程規劃")
def trip_plan(ctx, city: str):
    registry = ToolRegistry.global_instance()
    weather = registry.get("weather.query")
    ctx.set("latest_city", city)
    return weather(city=city)
```

預設會使用惰性初始化的全域 Registry，進階使用者仍可手動建立 `ToolRegistry()`，並透過 decorator 的 `registry` 參數覆寫使用的實例。

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

## 與 Claude Desktop 的自動註冊整合

ToolAnything 內建輕量 MCP Tool Server，可透過 CLI 一鍵啟動並生成 Claude Desktop 設定：

- 啟動 MCP Server：

  ```bash
  toolanything run-mcp --port 9090
  ```

  伺服器提供 `/health`、`/tools` 與 `POST /invoke` 三個端點，預設監聽 `0.0.0.0`，可透過 `--host` 覆寫。

- 產生 Claude Desktop 設定片段：

  ```bash
  toolanything init-claude
  ```

  指令會在當前路徑生成 `claude_desktop_config.json`（如需覆寫可加上 `--force`），內容如下：

  ```json
  {
    "mcpServers": {
      "toolanything": {
        "command": "python",
        "args": ["-m", "toolanything.server.mcp_tool_server", "--port", "9090"],
        "autoStart": true
      }
    }
  }
  ```

將此片段加入 Claude Desktop 設定檔（例如 macOS 的 `~/Library/Application Support/Claude/config.json`）並重新啟動，即可自動載入 ToolAnything 所提供的所有工具。

- 直接安裝 MCP 設定到 Claude Desktop：

  ```bash
  toolanything install-claude --config "~/Library/Application Support/Claude/config.json" --port 9090
  ```

  指令會讀取（或建立）指定的 Claude Desktop 設定檔，將 `mcpServers.toolanything` 自動寫入，重新啟動 Claude Desktop 後即可套用，無需手動複製貼上。
