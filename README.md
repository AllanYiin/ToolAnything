# ToolAnything

> **ToolAnything for Modern AI Toolchains**

ToolAnything 是給 AI 開發工程師的工具層。你定義一次 tool，就可以同時接上 **MCP** 與 **OpenAI tool calling**，不用自己再維護兩套 schema、兩套名稱映射、兩套執行迴圈。

它的目標不是再做一個 agent framework，而是把最麻煩、最重複的那層 **tool integration glue code** 抽掉：

- 把 Python function 直接變成 MCP / OpenAI 可用的 tool
- 把 HTTP API、SQL、PyTorch / ONNX inference 直接註冊成 tool
- 內建 `serve`、`doctor`、`inspect`，方便你啟動、診斷、驗證
- 內建 `OpenAIChatRuntime`，不只輸出 schema，還能直接跑 OpenAI tool loop

如果你正在做：

- AI agent / assistant 的工具層
- MCP server 或 MCP-compatible integration
- OpenAI function calling / tool calling 整合
- 把既有 API、SQL 或 model inference 封裝成可呼叫工具

這個 repo 值得你看。

## 為什麼用 ToolAnything

### 你實際省掉的是什麼

不用 ToolAnything 時，你通常要自己做：

1. 定義 Python function 或外部 API wrapper
2. 產生 OpenAI tool schema
3. 產生 MCP tool schema
4. 處理名稱合法化與映射
5. 寫 tool execution runtime
6. 補 `stdio` / HTTP transport
7. 再做 smoke test、inspector 與 Claude Desktop 設定

ToolAnything 把這些常見重工收斂成一套。

### 核心價值

| 能力 | 對開發者的價值 |
| --- | --- |
| 一次定義，同時輸出 MCP 與 OpenAI | 少維護兩套 integration，避免 schema 漂移 |
| Source-based tools | 可以直接包 HTTP、SQL、model，不必再手寫 wrapper function |
| `OpenAIChatRuntime` | 不只「能 export tools」，而是可以直接跑 tool loop |
| MCP transports | 同時支援 `stdio`、Streamable HTTP 與 legacy SSE/HTTP |
| `doctor` / `inspect` | 導入時更快驗證 initialize、tools/list、tools/call |
| Tool search / metadata / strategy | 工具數量增加後仍能做篩選與策略化選擇 |

## 這個專案適合誰

適合：

- 想把既有 Python function 快速暴露成 AI tools 的工程師
- 要同時支援 MCP 與 OpenAI tool calling 的產品 / 平台團隊
- 想把 REST API、SQL query、model inference 變成正式 tool source 的團隊
- 想要一套帶有 CLI、診斷與測試工具的 tool runtime

不適合：

- 你只需要一次性的單一 OpenAI schema 輸出
- 你要的是完整 agent orchestration / memory / workflow platform
- 你只想要 UI，不想碰 Python tool runtime

## 5 分鐘看懂它怎麼用

### 先看最極端版本：1 分鐘做出一個 MCP server

如果你已經裝好 Python 與 ToolAnything，做一個可被 MCP host 呼叫的 server，最短可以只要一個檔案加一條命令。

```python
from toolanything import tool


@tool(name="calculator.add", description="加總兩個整數")
def add(a: int, b: int) -> int:
    return a + b
```

```bash
toolanything serve tools.py --stdio
```

這樣就已經不是「只有一個 Python function」，而是一個有 `tools/list`、`tools/call`、schema 匯出與 stdio transport 的 MCP server。

你沒有手寫的部分包括：

- tool registration
- input schema 生成
- MCP tool definition 匯出
- `tools/call` 路由
- 回傳值序列化
- stdio server plumbing

如果要更誠實地說：

- `1 分鐘`：你已經裝好環境，只是在把一個函式暴露成 MCP tool
- `3 分鐘`：你從 clone repo 到第一次本機跑通 `serve`

### 1. 安裝

目前最穩定的使用方式是直接從 repo 安裝：

```bash
git clone <your-fork-or-this-repo>
cd ToolAnything
pip install -e .
```

需要測試工具時：

```bash
pip install -e .[dev]
```

需求：

- Python `>=3.10`

### 2. 定義一個 tool

```python
from toolanything import tool


@tool(name="weather.query", description="取得城市天氣")
def get_weather(city: str, unit: str = "c") -> dict:
    return {"city": city, "unit": unit, "temp": 25}
```

### `@tool` 的語法糖到底省了什麼

`@tool` 的價值不是幫你少打一份 JSON，而是把「Python function 變成 MCP tool」這件事裡，大部分重複且低價值的整合工作自動化。

以這段函式為例：

```python
import toolanything
@tool(name="weather.query", description="取得城市天氣")
def get_weather(city: str, unit: str = "c") -> dict:
    """查詢指定城市的即時天氣。"""
    return {"city": city, "unit": unit, "temp": 25}
```

ToolAnything 目前會自動把它映射到 MCP tool definition 的核心部分：

| Python 宣告 | ToolAnything 自動處理 | 對應到 MCP |
| --- | --- | --- |
| `name="weather.query"` | 註冊穩定 tool name | `name` |
| `description=...` 或 docstring 摘要 | 組合對外描述文字 | `description` |
| `city: str`, `unit: str = "c"` | 由 type hints 與 default 產生 JSON Schema | `input_schema`（tool input schema） |
| 函式本體 | 包成可被 registry / runtime 呼叫的 invoker | `tools/call` 的執行目標 |

換句話說，`@tool` 不是把 Python function 生硬包成字典，而是把「定義、註冊、schema、執行入口」一次接好。

### 3. 啟動 MCP server

```bash
toolanything serve examples/quickstart/tools.py --stdio
```

或啟動 HTTP transport：

```bash
toolanything serve examples/quickstart/tools.py --host 127.0.0.1 --port 9090
```

### 4. 驗證 transport 與 tool call

```bash
toolanything doctor --mode stdio --tools examples.quickstart.tools
```

### 5. 直接跑 OpenAI tool loop

```python
from toolanything import OpenAIChatRuntime

runtime = OpenAIChatRuntime()
result = runtime.run(
    model="gpt-4.1-mini",
    prompt="請呼叫 weather.query，城市是台北",
)
print(result["final_text"])
```

## 從 Python function 到 MCP tool：隱形成本與可見責任

### ToolAnything 幫你隱形處理掉的技術議題

- 解析函式簽名與 type hints，產生 MCP / OpenAI 共用的 JSON Schema
- 根據 default 值區分 required / optional 參數
- 自動略過 `self`、`cls` 與 context 參數，避免把內部實作細節暴露成 tool input
- 從 `description` 或 docstring 摘要補齊對外說明
- 把函式註冊進 registry，接上 MCP `tools/list` 與 `tools/call`
- 將 Python 回傳值序列化成 MCP 可回傳的內容格式
- 統一處理工具執行錯誤與未預期例外，避免每個 tool 各寫一套錯誤外殼
- 在 `serve` 模式下補上 MCP capability / server info / transport plumbing
- 在 OpenAI 路徑下同步輸出 tool schema，並可直接接到內建 tool-calling runtime

### 開發者仍然要自己處理的可見議題

- 工具的業務邏輯是否正確，回傳結果是否真的能支撐 agent 決策
- tool name、description、參數命名是否清楚且穩定
- 外部 API、資料庫、模型權限與金鑰管理
- 重試、超時、rate limit、成本控制與副作用管理
- 工具輸出的資料結構設計，尤其是給 LLM 消費時的穩定性與可讀性
- 部署策略與 host 整合選擇，例如要用 `stdio` 還是 HTTP transport
- 若走 OpenAI tool calling，system prompt、tool policy 與模型選型仍需自己負責

重點是：**ToolAnything 幫你消掉的是 integration glue，不是業務判斷。**  
你應該把心力放在「這個 tool 該不該存在、契約怎麼設計、結果怎麼讓模型可靠使用」，而不是反覆手刻 schema、registry 與 protocol plumbing。

## 產品輪廓

ToolAnything 可以分成四層理解：

1. **Tool definition layer**
   你用 `@tool` 或 source-based API 宣告工具。
2. **Runtime layer**
   ToolAnything 負責 schema、執行、名稱映射與 tool loop。
3. **Transport layer**
   同一份工具可透過 MCP `stdio`、Streamable HTTP、legacy SSE/HTTP 暴露。
4. **Developer tooling**
   `serve`、`doctor`、`inspect`、Claude Desktop 設定安裝與 examples。

這個分層的重點是：**你在寫的是 tool，不是在重複寫整合。**

## 主要功能

### 1. 一份工具，同時支援 MCP 與 OpenAI

ToolAnything 內建：

- MCP schema export
- OpenAI tool schema export
- OpenAI-safe tool name mapping
- Tool invocation runtime
- OpenAI tool-calling roundtrip runtime

對應實作：

- [openai_adapter.py](src/toolanything/adapters/openai_adapter.py)
- [mcp_adapter.py](src/toolanything/adapters/mcp_adapter.py)
- [openai_runtime.py](src/toolanything/openai_runtime.py)

### 2. 不只 function，也支援外部來源

你可以直接把下面這些來源變成 tool：

- HTTP API
- SQL query
- PyTorch model inference
- ONNX model inference

相關範例：

- [http_tool.py](examples/non_function_tools/http_tool.py)
- [sql_tool.py](examples/non_function_tools/sql_tool.py)
- [onnx_tool.py](examples/non_function_tools/onnx_tool.py)
- [pytorch_tool.py](examples/non_function_tools/pytorch_tool.py)

### 3. MCP transport 不只一種

目前支援：

| Transport | 用途 |
| --- | --- |
| `stdio` | Claude Desktop、IDE、本機 agent host 最直接 |
| Streamable HTTP | 新版 MCP HTTP transport，建議做網路型整合時使用 |
| legacy SSE / HTTP | 舊 client 相容層 |

### 4. 內建診斷與檢查工具

#### `doctor`

快速驗證：

- transport 是否接通
- `initialize`
- `tools/list`
- `tools/call`

```bash
toolanything doctor --mode http --url http://localhost:9090
```

#### `inspect`

啟動內建 Web inspector：

```bash
toolanything inspect
```

它適合：

- 探索工具 schema
- 手動測 tool arguments
- 看 MCP transcript
- 做 OpenAI tool-calling smoke test

## OpenAI tool calling

這裡是 ToolAnything 跟一般「只會吐 schema 的 helper」最大差異之一。

你可以只拿 schema：

```python
from toolanything.adapters import OpenAIAdapter
from toolanything.core.registry import ToolRegistry

adapter = OpenAIAdapter(ToolRegistry.global_instance())
tools = adapter.to_schema()
```

也可以直接用內建 runtime 跑完整 tool loop：

```python
from toolanything import OpenAIChatRuntime

runtime = OpenAIChatRuntime()
result = runtime.run(
    model="gpt-4.1-mini",
    prompt="請用工具回答問題",
    system_prompt="如果工具可以回答，就優先使用工具。",
)
```

相關範例：

- [dual_protocol_demo.py](examples/opencv_mcp_web/dual_protocol_demo.py)

## MCP 使用方式

### 啟動 stdio

```bash
toolanything serve examples/quickstart/tools.py --stdio
```

### 啟動 Streamable HTTP

```bash
toolanything serve examples/quickstart/tools.py --streamable-http --host 127.0.0.1 --port 9092
```

### 啟動 legacy HTTP / SSE

```bash
toolanything serve examples/quickstart/tools.py --host 127.0.0.1 --port 9090
```

更多 transport 細節請看：

- [architecture-walkthrough.md](docs/architecture-walkthrough.md)
- [examples/mcp_transports/README.md](examples/mcp_transports/README.md)
- [examples/streamable_http/README.md](examples/streamable_http/README.md)

## Examples

如果你第一次接觸這個 repo，建議照這個順序看：

| 路線 | 入口 | 你會學到什麼 |
| --- | --- | --- |
| Quickstart | [examples/quickstart/README.md](examples/quickstart/README.md) | 最短路徑跑通 tool 定義、serve、search、call |
| Streamable HTTP | [examples/streamable_http/README.md](examples/streamable_http/README.md) | 新版 MCP HTTP transport 的 handshake 與 session lifecycle |
| MCP Transports | [examples/mcp_transports/README.md](examples/mcp_transports/README.md) | 三種 transport 的差異、用途、與 client 開發最小握手 |
| Tool Selection | [examples/tool_selection/README.md](examples/tool_selection/README.md) | metadata、constraints、strategy 與 semantic retrieval |
| Protocol Boundary | [examples/protocol_boundary/README.md](examples/protocol_boundary/README.md) | protocol core 與 transport 的責任切割 |
| Non-function Tools | [examples/non_function_tools/README.md](examples/non_function_tools/README.md) | 直接把 API、SQL、model 變成 tool |
| OpenCV Web Demo | [examples/opencv_mcp_web/README.md](examples/opencv_mcp_web/README.md) | 較完整的 MCP + OpenAI 雙協議範例 |

## Claude Desktop 整合

ToolAnything 內建兩種方式：

### 產生設定片段

```bash
toolanything init-claude --module examples/opencv_mcp_web/server.py --port 9091
```

### 直接寫入設定檔

```bash
toolanything install-claude --config "~/Library/Application Support/Claude/config.json" --port 9090 --module examples/opencv_mcp_web/server.py
```

如果你的目標是讓 MCP Desktop 類型 host 直接吃 stdio，這會比手動抄設定穩定很多。

## 遷移與相容性

如果你已經在用舊的 callable-first 方式，現在仍然可以繼續用：

- `@tool`
- `ToolSpec.from_function()`
- `ToolRegistry.get() -> callable`
- `ToolRegistry.execute_tool_async()`

但新功能建議優先採用 source-based API。

詳細說明：

- [migration-guide.md](docs/migration-guide.md)

## 架構與設計

如果你正在評估「這東西能不能撐長期維護」，再往下讀這份文件：

- [architecture-walkthrough.md](docs/architecture-walkthrough.md)

你會看到：

- 為什麼 protocol core 與 transport 分開
- 為什麼從 callable-first 轉向 invoker-first
- 如何新增 transport
- 如何新增 source
- 如何新增 tool search strategy

這些內容應該放在第二層閱讀，而不是 README 首屏；但如果你在乎可擴充性，這份文件很重要。

## 專案狀態

目前 `pyproject.toml` 中的版本是 `0.1.0`，定位仍偏早期，但已具備完整可跑的：

- tool definition
- MCP transports
- OpenAI tool runtime
- doctor / inspect
- examples 與 migration 文件

如果你是要評估導入，最合理的方式不是先看 roadmap，而是先跑：

1. [examples/quickstart/README.md](examples/quickstart/README.md)
2. `toolanything doctor`
3. [examples/opencv_mcp_web/dual_protocol_demo.py](examples/opencv_mcp_web/dual_protocol_demo.py)

## 文件索引

- [docs/docs-map.md](docs/docs-map.md)
- [architecture-walkthrough.md](docs/architecture-walkthrough.md)
- [migration-guide.md](docs/migration-guide.md)
- [mcp-test-client-spec.md](docs/mcp-test-client-spec.md)

## License

MIT
