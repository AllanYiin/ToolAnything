# ToolAnything

ToolAnything 是一個「跨協議 AI 工具中介層」，開發者只需撰寫一次函數即可同時被 OpenAI Tool Calling 與 MCP 使用。專案核心特色包含：

- 單一函數、雙協議兼容：使用 `@tool` decorator 註冊後即可直接輸出 OpenAI/MCP schema。
- invoker-first 核心：工具 contract、source、invoker、runtime、transport 已分層，不再把 Python callable 當成唯一來源。
- source-based API：可直接把 HTTP API、SQL query、PyTorch / ONNX inference 註冊成 tool，不需要再手寫 wrapper function。
- 語法糖簡潔：依據 type hints 生成 JSON Schema，降低心智負擔。
- 支援 pipeline 與多使用者 state：透過 `@pipeline` decorator 組裝跨工具流程並維持使用者上下文。

👉 建議先閱讀 [Architecture Walkthrough](docs/architecture-walkthrough.md) 了解協議邊界與擴充方式。
👉 若你要從舊 `@tool` / callable-first API 遷移，先看 [Migration Guide](docs/migration-guide.md)。

## Learning Path（學習路徑）

### 1) 初學者路線：從 0 到第一個 Tool

**對應 examples 入口**：[`examples/quickstart/README.md`](examples/quickstart/README.md)

**閱讀順序**
1. [`examples/quickstart/README.md`](examples/quickstart/README.md) → `00_setup.md` → `01_define_tools.py` → `02_run_server.py` → `03_search_and_call.py`：最小可跑流程。  
2. [`src/toolanything/decorators/tool.py`](src/toolanything/decorators/tool.py)：`tool()` decorator 註冊入口。  
3. [`src/toolanything/core/models.py`](src/toolanything/core/models.py)：`ToolSpec` 的工具描述結構。  
4. [`src/toolanything/cli.py`](src/toolanything/cli.py)：`toolanything search` 與 `toolanything serve`。  

**讀完能做到什麼**
- 可以新增第一個 tool，透過 CLI search 找到它，並用 MCP `tools/call` 呼叫。

### 2) 已懂 MCP/JSON-RPC 的路線：掌握協議邊界

**對應 examples 入口**：[`examples/protocol_boundary/README.md`](examples/protocol_boundary/README.md)

**閱讀順序**
1. [`src/toolanything/server/mcp_tool_server.py`](src/toolanything/server/mcp_tool_server.py) 與 [`src/toolanything/server/mcp_stdio_server.py`](src/toolanything/server/mcp_stdio_server.py)：看 transport 如何注入依賴。  
2. [`src/toolanything/protocol/mcp_jsonrpc.py`](src/toolanything/protocol/mcp_jsonrpc.py)：`MCPJSONRPCProtocolCore.handle()` 的 method routing。  
3. [`docs/architecture-walkthrough.md`](docs/architecture-walkthrough.md#為什麼-protocol-要獨立指出-protocol-core-的入口與責任)：對照協議邊界與責任切割。  

**讀完能做到什麼**
- 能判斷應該在 protocol core、server/transport 或工具層擴充功能，而不改動核心路由。

### 3) 進階路線：工具搜尋與策略化選擇

**對應 examples 入口**：[`examples/tool_selection/README.md`](examples/tool_selection/README.md)

**閱讀順序**
1. [`src/toolanything/core/tool_search.py`](src/toolanything/core/tool_search.py)：`ToolSearchTool.search()` 入口。  
2. [`src/toolanything/core/selection_strategies.py`](src/toolanything/core/selection_strategies.py)：`BaseToolSelectionStrategy`、`RuleBasedStrategy`。  
3. [`src/toolanything/core/metadata.py`](src/toolanything/core/metadata.py)：`ToolMetadata` 與 `normalize_metadata()`。  
4. [`docs/architecture-walkthrough.md`](docs/architecture-walkthrough.md#tool-metadata-設計costlatency_hint_msside_effectcategorytagsextra與向下相容策略)：metadata 與策略章節整理。  

**讀完能做到什麼**
- 能自訂策略、限制 metadata 條件搜尋，並透過 `ToolSearchTool` 實作策略化工具選擇。  

## 協議對應方式（MCP STDIO / Streamable HTTP / SSE / OpenAI Tool Calling）

專案內同時支援 MCP STDIO、MCP Streamable HTTP、legacy MCP SSE / HTTP 與 OpenAI Tool Calling，其對應方式如下：

- **MCP STDIO**
  - 走 `MCPStdioServer`，透過 stdin/stdout 的 JSON-RPC 2.0 傳輸。
  - 與 URL 無關，屬於非 HTTP 通道。
  - 實作位置：`src/toolanything/server/mcp_stdio_server.py`
- **MCP Streamable HTTP**
  - 走 `POST /mcp` 與 `GET /mcp`，transport 只負責 HTTP/SSE 串流與 session/auth headers。
  - 為目前建議的 HTTP transport。
  - 實作位置：`src/toolanything/server/mcp_streamable_http.py`
- **MCP SSE / HTTP**
  - 走 HTTP 伺服器，MCP SSE 入口為 `GET /sse`，並透過 `POST /messages/{session_id}` 傳送 JSON-RPC。
  - 另提供簡化的 `POST /invoke/stream`（SSE）與 `POST /invoke` 介面，方便開發測試。
  - 已保留為 legacy compatibility layer。
  - 實作位置：`src/toolanything/server/mcp_tool_server.py`
- **OpenAI Tool Calling**
  - 走 schema 轉換（`OpenAIAdapter`），由程式產出工具定義給 OpenAI API。
  - 不依賴 URL，屬於資料格式與呼叫封裝的對接。
  - 實作位置：`src/toolanything/adapters/openai_adapter.py`

## Source-Based Tools

除了既有 `@tool` callable 用法，現在也支援 source-based API：

- HTTP：[`examples/http_tool.py`](examples/http_tool.py)
- SQL：[`examples/sql_tool.py`](examples/sql_tool.py)
- ONNX：[`examples/onnx_tool.py`](examples/onnx_tool.py)
- PyTorch：[`examples/pytorch_tool.py`](examples/pytorch_tool.py)

新 API 的核心是：

- `ToolContract`：對外 schema / metadata
- `SourceSpec`：來源設定
- `Invoker`：執行體
- `ExecutionContext`：runtime 注入上下文

## Connection Tester / Doctor

ToolAnything 提供 `doctor` 子命令，用來快速確認 transport 與 MCP 基本流程是否可用：

```bash
# stdio 模式：自動啟動 doctor 專用 server，含 __ping__ 工具
toolanything doctor --mode stdio --tools examples.quickstart.tools

# 自訂 stdio 啟動指令
toolanything doctor --mode stdio --cmd "python -m toolanything.cli run-stdio"


# http 模式：自動啟動 serve（SSE + JSON-RPC）
toolanything doctor --mode http --tools examples.quickstart.tools

# 連線既有 HTTP server

toolanything doctor --mode http --url http://localhost:9090
```

輸出會包含每個步驟的 PASS/FAIL、耗時與錯誤建議，便於快速定位 transport、initialize、tools/list、tools/call 的問題。

## Built-in MCP Test Client

如果你需要互動式檢查，不想只看 CLI 報告，可以啟動內建 Web 版 `inspect`：

```bash
toolanything inspect
```

預設會在 `http://127.0.0.1:9060` 啟動本機測試介面並自動開啟瀏覽器。可用參數：

```bash
# 指定 host / port，且不要自動開瀏覽器
toolanything inspect --host 127.0.0.1 --port 9061 --no-open

# 調整 inspector 預設 timeout
toolanything inspect --timeout 12
```

`inspect` 和 `doctor` 的定位不同：

- `doctor`：偏 CLI smoke test，適合 CI、快速檢查 initialize / tools/list / tools/call。
- `inspect`：偏互動式測試台，支援切換 `http` / `stdio`、瀏覽工具 schema、手動呼叫工具，並可選填 OpenAI API key 測試模型是否會正確調工具。

目前 `inspect` v1 的限制：

- 僅支援 `MCP HTTP SSE` 與 `STDIO`。
- LLM 模式目前只支援 OpenAI API。
- API key 不會存進 localStorage，只存在單次 request 記憶體中。
- 這不是官方 MCP Inspector 的完整替代品，暫不提供 raw traffic replay、resources/prompts explorer。

## 快速範例

```python
from toolanything import tool, pipeline, ToolRegistry, StateManager

state_manager = StateManager()

# 不需額外指定 registry，會自動使用全域預設註冊表
@tool(name="weather.query", description="取得城市天氣")
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

## Examples（情境入口清單）

- **Quickstart：從零跑通 MCP 基本流程**  
  入口：[`examples/quickstart/README.md`](examples/quickstart/README.md)  
  目標：定義工具 → 啟動 server → tools/list → CLI search → tools/call。  

- **Tool Selection：metadata 與策略化搜尋**  
  入口：[`examples/tool_selection/README.md`](examples/tool_selection/README.md)  
  目標：用 metadata 建立工具目錄、練習搜尋條件與自訂策略。  

- **Protocol Boundary：協議邊界與 transport 對照**  
  入口：[`examples/protocol_boundary/README.md`](examples/protocol_boundary/README.md)  
  目標：理解 protocol/core 與 server/transport 的責任分界。  

- **進階示例（閱讀時機：完成 Quickstart 後）**  
  - `examples/demo_mcp.py`：最小 MCP HTTP server demo。  
  - `examples/demo_mcp_stdio.py`：MCP stdio demo。  
  - `examples/http_tool.py`：宣告式 HTTP tool。  
  - `examples/sql_tool.py`：宣告式 SQL tool。  
  - `examples/onnx_tool.py`：ONNX model tool。  
  - `examples/pytorch_tool.py`：PyTorch model tool。  
  - `examples/weather_tool/`：天氣工具模組。  
  - `examples/opencv_mcp_web/`：OpenCV MCP Web 外部範例（檔案路徑工作流）。  

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

## 下一步（Roadmap）

- [ ] **擴充 CLI（tool search / strategy / metadata）**
  - [ ] `toolanything search` 新增 `--strategy` 參數，能選擇 `rule-based` / `weighted` 等策略，並明確指出會影響 metadata 條件篩選的行為。
  - [ ] 增加 `toolanything search --metadata` 範例輸出說明（例如 `max-cost`、`latency-budget-ms`、`allow-side-effects`、`category` 與 tags），並補齊與 ToolSelection strategy 的關聯。
  - [ ] `toolanything explain-search`（非破壞性子命令）輸出當前搜尋條件與策略、metadata 的對應說明，便於除錯。
  - [ ] `toolanything examples` 提供 examples 入口導覽（連結與簡介）。
- [ ] **擴充文件（docs/）**
  - [ ] 補齊 [`docs/architecture-walkthrough.md`](docs/architecture-walkthrough.md) 的「Tool Search 與 Strategy」章節，連到 metadata 與策略實作。
  - [ ] 新增 `docs/cli-reference.md`：列出所有子命令、flag、使用情境與 `See also` 對應 examples。
  - [ ] 更新 [`docs/README.md`](docs/README.md) 索引，補上 Learning Path 與 examples 導覽。
- [ ] **擴充 examples 目錄**
  - [ ] [`examples/quickstart/README.md`](examples/quickstart/README.md)：補上一步步執行指令與預期輸出片段。
  - [ ] [`examples/tool_selection/README.md`](examples/tool_selection/README.md)：新增 metadata/constraints/strategy 三條路徑的差異示範。
  - [ ] [`examples/protocol_boundary/README.md`](examples/protocol_boundary/README.md)：整理 protocol/core 與 server/transport 的對照清單與示意。
- [ ] 撰寫更多自動化測試涵蓋 decorator 與 adapter。
- [ ] 引入 SecurityManager、ResultSerializer 等擴展點的實際應用範例。
- [ ] `skill as tool` 的 source / contract / runtime 設計。

## 相依套件說明

- 執行與測試時會隨套件一併安裝 `tenacity`、`pytest` 與 `pytest-asyncio`，確保非同步測試所需外掛始終可用（詳見 `requirements.txt` 與 `pyproject.toml`）。
- `http.server`、`urllib`、`asyncio`、`dataclasses` 等皆為 Python 標準庫模組，隨 CPython 內建提供，無需額外安裝或列入 requirements。

## 與 Claude Desktop 的自動註冊整合

ToolAnything 內建輕量伺服器，可透過 CLI 載入 `@tool` 模組或外部 Python 檔案，並生成 Claude Desktop 設定：

- 啟動工具伺服器（載入工具模組）：

  ```bash
  toolanything serve your_module --port 9090
  toolanything serve examples/opencv_mcp_web/server.py --port 9091
  ```

  伺服器提供 `/health`、`/tools`、`GET /sse`、`POST /messages/{session_id}`、`POST /invoke` 與 `POST /invoke/stream` 等端點，預設監聽 `127.0.0.1`，可透過 `--host` 覆寫。
  HTTP transport 會驗證 `Origin`；如需自訂允許來源，可設定 `TOOLANYTHING_ALLOWED_ORIGINS`（逗號分隔）。
  若要讓 SSE session 維持特定使用者狀態，可用 `GET /sse?user_id=your-user-id` 建立 session；STDIO 模式可用 `TOOLANYTHING_USER_ID` 指定預設使用者。

- 產生 Claude Desktop 設定片段：

  ```bash
  toolanything init-claude --module your_module
  toolanything init-claude --module examples/opencv_mcp_web/server.py --port 9091
  ```

  指令會在當前路徑生成 `claude_desktop_config.json`（如需覆寫可加上 `--force`），內容如下：

  ```json
  {
    "mcpServers": {
      "toolanything": {
        "command": "python",
        "args": ["-m", "toolanything.cli", "serve", "your_module", "--stdio", "--port", "9090"],
        "autoStart": true
      }
    }
  }
  ```

將此片段加入 Claude Desktop 設定檔（例如 macOS 的 `~/Library/Application Support/Claude/config.json`）並重新啟動，即可自動載入 ToolAnything 所提供的所有工具。

- 直接安裝 MCP 設定到 Claude Desktop：

  ```bash
  toolanything install-claude --config "~/Library/Application Support/Claude/config.json" --port 9090 --module your_module
  ```

  指令會讀取（或建立）指定的 Claude Desktop 設定檔，將 `mcpServers.toolanything` 自動寫入，重新啟動 Claude Desktop 後即可套用，無需手動複製貼上。若你要安裝 repo 內範例，直接把 `--module` 指向外部檔案路徑即可，例如 `examples/opencv_mcp_web/server.py`。
