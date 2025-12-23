# ToolAnything

ToolAnything 是一個「跨協議 AI 工具中介層」，開發者只需撰寫一次函數即可同時被 OpenAI Tool Calling 與 MCP 使用。專案核心特色包含：

- 單一函數、雙協議兼容：使用 `@tool` decorator 註冊後即可直接輸出 OpenAI/MCP schema。
- 語法糖簡潔：依據 type hints 生成 JSON Schema，降低心智負擔。
- 支援 pipeline 與多使用者 state：透過 `@pipeline` decorator 組裝跨工具流程並維持使用者上下文。

## 協議對應方式（MCP STDIO / SSE / OpenAI Tool Calling）

專案內同時支援 MCP STDIO、MCP HTTP（含 SSE）與 OpenAI Tool Calling，其對應方式如下：

- **MCP STDIO**
  - 走 `MCPStdioServer`，透過 stdin/stdout 的 JSON-RPC 2.0 傳輸。
  - 與 URL 無關，屬於非 HTTP 通道。
  - 實作位置：`src/toolanything/server/mcp_stdio_server.py`
- **MCP SSE / HTTP**
  - 走 HTTP 伺服器，SSE 端點為 `POST /invoke/stream`。
  - 以 URL 路徑區分 SSE 與非串流（`POST /invoke`）。
  - 實作位置：`src/toolanything/server/mcp_tool_server.py`
- **OpenAI Tool Calling**
  - 走 schema 轉換（`OpenAIAdapter`），由程式產出工具定義給 OpenAI API。
  - 不依賴 URL，屬於資料格式與呼叫封裝的對接。
  - 實作位置：`src/toolanything/adapters/openai_adapter.py`

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

## 工具介面類型支援與規範

Schema 引擎會依據函數的 type hints 生成 JSON Schema，支援項目如下：

- 基本型別：`str`、`int`、`float`、`bool`、`list`、`dict` 會映射到對應的 JSON Schema `type`。
- 容器型別：`list[T]`、`tuple[T]` 會產生 `items`，`dict[key, value]` 會以 `additionalProperties` 描述 value 類型。
- 合併型別：`Union[...]` 或 `Optional[T]` 會轉成 `oneOf`，同時保留 `null` 以表示可選值。
- 限定值：`Literal[...]` 與 `Enum` 會輸出 `enum` 陣列；若 Enum 值為基本型別，會附帶對應的 `type` 方便驗證。

若使用未支援或自訂類別，Schema 會回退為字串型別。建議在工具內自行序列化複雜物件，或改用基本型別、巢狀 `dict/list` 來描述資料結構，以確保工具在各協議下的可攜性與檢驗一致性。

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

## 相依套件說明

- 執行與測試時會隨套件一併安裝 `tenacity`、`pytest` 與 `pytest-asyncio`，確保非同步測試所需外掛始終可用（詳見 `requirements.txt` 與 `pyproject.toml`）。
- `http.server`、`urllib`、`asyncio`、`dataclasses` 等皆為 Python 標準庫模組，隨 CPython 內建提供，無需額外安裝或列入 requirements。

## 與 Claude Desktop 的自動註冊整合

ToolAnything 內建輕量 MCP Tool Server，可透過 CLI 一鍵啟動並生成 Claude Desktop 設定：

- 啟動 MCP Server：

  ```bash
  toolanything run-mcp --port 9090
  ```

  伺服器提供 `/health`、`/tools`、`POST /invoke` 與 `POST /invoke/stream`（SSE）四個端點，預設監聽 `0.0.0.0`，可透過 `--host` 覆寫。

  其中 `/invoke/stream` 會以 `text/event-stream` 回傳工具結果，可用於需要 SSE 的連線器。

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
        "args": ["-m", "toolanything.cli", "run-mcp", "--port", "9090"],
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

- 直接安裝 OpenCV MCP Web 範例到 Claude Desktop：

  ```bash
  toolanything install-claude-opencv --config "~/Library/Application Support/Claude/config.json" --port 9091
  ```

  指令會讀取（或建立）指定的 Claude Desktop 設定檔，將 `mcpServers.opencv_mcp_web` 自動寫入，重新啟動 Claude Desktop 後即可套用。
