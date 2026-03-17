# ToolAnything

> 一次定義工具，同時接上 MCP 與 OpenAI tool calling。

ToolAnything 是一個給 LLM 應用開發者的 Python 工具層。它把最容易失控的整合工作收斂成一套：工具定義、schema 生成、名稱映射、執行 runtime、MCP transport，以及本機診斷與驗證流程。

如果你正在做 agent、assistant、copilot 或內部 AI 平台，通常真正拖慢進度的不是模型 API 本身，而是這些重複工作：

- 同一個 tool 要維護兩套 schema
- Python function、class method、HTTP API、SQL、model inference 都要各自包 wrapper
- tool 可以宣告，但不容易用真實 MCP host 或 OpenAI loop 驗證
- transport、debug、Claude Desktop 設定與 smoke test 都變成額外成本

ToolAnything 的目標不是再做一個全能 agent framework，而是把這一層 integration glue code 拿掉，讓你把心力放回工具契約、產品邏輯與模型行為。

## 給 coding agent 的入口

如果你是讓 Codex、OpenClaw、Claude Code 或其他 coding agent 直接讀 repo，先看這幾份：

- [AGENTS.md](AGENTS.md)：通用選型規則、最短 quickstart、何時用 `@tool`、何時用 source-based API
- [OPENCLAW.md](OPENCLAW.md)：OpenClaw 的 skill routing、metadata 與 shared server 規則
- [CLAUDE.md](CLAUDE.md)：Claude Code / Claude Desktop 的本地整合與 `install-claude`
- [llms.txt](llms.txt)：文件地圖、quickstart、migration、verification 索引

## 為什麼 LLM 開發者會想用它

### 1. 一次定義，同時接 MCP 與 OpenAI

你可以用一份工具定義，同時得到：

- MCP tool schema
- OpenAI tool schema
- CLI command tree
- OpenAI-safe tool name mapping
- 一套共用的工具執行 runtime

這可以直接減少雙協議整合時最常見的 schema drift 問題。

### 1.5 同一份 ToolContract 也能直接變成 CLI

如果你想在 shell、CI 或人工 smoke test 直接跑工具，不需要再自己包 argparse：

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools
toolanything cli run --config toolanything.cli.json -- math add --a 2 --b 3 --json
```

CLI 仍走同一個 registry / runtime / invoker 執行鏈，不會分叉成另一套邏輯。

### 2. 不只包 Python function / class method，也能直接包外部來源

ToolAnything 不把「tool = Python function」當成唯一前提。除了 `@tool` 直接裝飾 Python function 與 class method，也支援把這些來源直接註冊成正式工具：

- HTTP API
- SQL query
- PyTorch inference
- ONNX inference

這對已經有既有服務、資料庫查詢或模型資產的團隊特別有價值，因為你不必先手寫一層低價值 wrapper 才能把它接進 LLM toolchain。

### 3. 不只輸出 schema，還能真的跑起來

這個 repo 的定位不是 schema helper。它同時提供：

- `toolanything serve`：啟動 MCP server
- `toolanything doctor`：檢查 initialize、`tools/list`、`tools/call`
- `toolanything inspect`：用內建 Web inspector 直接測工具與 MCP transcript
- `toolanything cli`：把 ToolContract 匯出為 CLI app 並直接執行
- `OpenAIChatRuntime`：直接跑 OpenAI tool loop

也就是說，你不只可以「宣告工具」，還能用同一套工具做本機驗證、host 整合與 OpenAI roundtrip 測試。

### 4. 有意識地把責任切乾淨

ToolAnything 幫你處理的是 integration 與 protocol plumbing，不是替你決定 agent orchestration。

它很適合拿來做：

- AI 產品的工具層
- MCP server
- 雙協議工具輸出層
- 可重用的 tool runtime

它不打算直接取代：

- workflow / memory / planning framework
- 完整 agent platform
- 產品 UI

這個邊界反而是優勢，因為你比較不會被迫接受一整套過重的抽象。

## 你實際省掉的是什麼

沒有 ToolAnything 時，常見流程通常長這樣：

1. 定義 Python function、class method 或外部 API wrapper
2. 產生 OpenAI tools schema
3. 產生 MCP tools schema
4. 處理 tool name mapping 與合法化
5. 寫一套 tool execution loop
6. 補 `stdio` 或 HTTP transport
7. 再補 diagnosis、inspect、Claude Desktop 設定與 smoke test

用 ToolAnything 時，這些工作會被收斂進同一套 API、runtime 與 CLI。

## 這個專案最適合誰

適合：

- 想把既有 Python function / class method 快速暴露成 MCP / OpenAI tools 的開發者
- 需要同時支援 MCP 與 OpenAI tool calling 的產品團隊
- 想把 REST API、SQL、model inference 轉成正式 tool source 的平台團隊
- 希望工具層本身就帶有 CLI、diagnostics 與 examples 的開發者

不適合：

- 你只需要一次性的 schema 匯出
- 你要的是完整 agent orchestration / workflow / memory 平台
- 你不打算碰 Python runtime，只想找純前端或純 SaaS 型方案

## 60 秒看懂核心體驗

### Step 1: 定義一個 tool

`@tool` 目前支援：

- module-level function
- class method（`@tool` 與 `@classmethod` 兩種順序都可）

```python
from toolanything import tool


@tool(
    name="calculator.add",
    description="加總兩個整數",
    cli_command="calc add",
)
def add(a: int, b: int) -> int:
    return a + b
```

如果你希望 CLI 指令名和 tool name 分開，直接在 `@tool(...)` 補 `cli_command` 即可；CLI export config 的 `command_overrides` 仍可做最後覆寫。

### Step 2: 啟動成 MCP server

```bash
toolanything serve tools.py --streamable-http --host 127.0.0.1 --port 9092
```

### Step 3: 驗證它真的可呼叫

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
```

做到這裡時，你已經不是只有一個 Python function / class method，而是一個可以被 MCP host 發現與呼叫的工具服務，包含：

- `tools/list`
- `tools/call`
- input schema 生成
- 回傳值序列化
- Streamable HTTP transport

## 安裝

預設安裝路徑就是 PyPI：

```bash
pip install toolanything
```

如果你是這個 repo 的貢獻者，才改用 editable install：

```bash
git clone <this-repo>
cd ToolAnything
pip install -e .[dev]
```

`.[dev]` 會額外安裝測試與 model tool 需要的套件，例如 `httpx`、`onnx`、
`onnxruntime`、`torch`，避免測試收集階段因缺少依賴而失敗。

需求：

- Python `>=3.10`

## 快速開始

### 1. 用 decorator 定義工具

`@tool` 可直接用在一般函數，也可用在 class method。class method 的完整教程見 [examples/class_method_tools/README.md](examples/class_method_tools/README.md)。

```python
from toolanything import tool


@tool(name="weather.query", description="取得城市天氣")
def get_weather(city: str, unit: str = "c") -> dict:
    return {"city": city, "unit": unit, "temp": 25}
```

### 2. 啟動 MCP server

```bash
toolanything serve examples/quickstart/tools.py --streamable-http --host 127.0.0.1 --port 9092
```

如果你要接 Claude Desktop 這類 Desktop host，再改用 stdio：

```bash
toolanything serve examples/quickstart/tools.py --stdio
```

### 3. 檢查 transport 與 tool call

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
```

或檢查 Desktop/stdio server：

```bash
toolanything doctor --mode stdio --tools examples.quickstart.tools
```

### 4. 開 inspector 做互動式驗證

```bash
toolanything inspect
```

它適合拿來：

- 看工具 schema
- 手動送 `tools/call`
- 檢查 MCP transcript
- 做 OpenAI tool-calling smoke test

## 直接跑 OpenAI tool loop

如果你不只想匯出 tool schema，也想直接讓模型透過工具回答：

```python
from toolanything import OpenAIChatRuntime

runtime = OpenAIChatRuntime()
result = runtime.run(
    model="gpt-4.1-mini",
    prompt="請使用 weather.query 回答問題。",
)

print(result["final_text"])
```

## 不只 function，也支援 source-based tools

如果你的工具不是 Python function / class method，而是既有服務或資產，可以直接走 source-based API。

支援範圍：

- HTTP source
- SQL source
- Model source

相關範例：

- [examples/non_function_tools/http_tool.py](examples/non_function_tools/http_tool.py)
- [examples/non_function_tools/sql_tool.py](examples/non_function_tools/sql_tool.py)
- [examples/non_function_tools/onnx_tool.py](examples/non_function_tools/onnx_tool.py)
- [examples/non_function_tools/pytorch_tool.py](examples/non_function_tools/pytorch_tool.py)

如果你是從既有 callable-first 寫法遷移過來，舊用法仍可繼續使用；新功能則建議優先採用 source-based API。詳見 [docs/migration-guide.md](docs/migration-guide.md)。

## 核心能力一覽

| 能力 | 對開發者的價值 |
| --- | --- |
| 一份工具同時支援 MCP 與 OpenAI | 降低雙協議維護成本，避免 schema 漂移 |
| `@tool` 與 source-based API 並存 | 先用簡單方式上手，再逐步接 HTTP / SQL / model |
| `OpenAIChatRuntime` | 不只輸出 schema，還能直接跑 tool loop |
| `stdio`、Streamable HTTP、legacy SSE/HTTP | 可以依 host 與部署情境切換 transport |
| `doctor`、`inspect`、Claude Desktop integration | 導入與除錯成本更低 |
| tool metadata 與 search strategy | 工具數量變多後仍可做篩選、排序與策略化選擇 |

## MCP transport 支援

| Transport | 典型場景 |
| --- | --- |
| `stdio` | Claude Desktop、IDE、本機 agent host |
| Streamable HTTP | 新版 MCP HTTP 整合，適合服務間連線 |
| legacy SSE / HTTP | 相容舊 client |

如果你要做新的 MCP 整合，預設先用 Streamable HTTP；只有 Desktop host 或既有舊 client 相容需求時再改用 stdio / legacy。

## 專案導覽

如果你第一次進 repo，建議照這個順序閱讀：

| 想解決的問題 | 先看哪裡 |
| --- | --- |
| 我要先跑通最小可用流程 | [examples/quickstart/README.md](examples/quickstart/README.md) |
| 我要理解不同 transport 差異 | [examples/mcp_transports/README.md](examples/mcp_transports/README.md) |
| 我要做新版 MCP HTTP 整合 | [examples/streamable_http/README.md](examples/streamable_http/README.md) |
| 我要把 HTTP / SQL / model 變成 tool | [examples/non_function_tools/README.md](examples/non_function_tools/README.md) |
| 我要做工具搜尋與選擇策略 | [examples/tool_selection/README.md](examples/tool_selection/README.md) |
| 我要理解架構與擴充點 | [docs/architecture-walkthrough.md](docs/architecture-walkthrough.md) |
| 我要評估遷移成本 | [docs/migration-guide.md](docs/migration-guide.md) |

## Claude Desktop 整合

產生設定片段：

```bash
toolanything init-claude --module examples/opencv_mcp_web/server.py --port 9090
```

直接寫入設定檔：

```bash
toolanything install-claude --module examples/opencv_mcp_web/server.py --port 9090
```

## CLI Export

如果你想把同一份工具定義直接變成命令列介面：

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools
toolanything cli run --config toolanything.cli.json -- math add --a 2 --b 3
```

也可以輸出 launcher：

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools --launcher .toolanything/mytools.py
python .toolanything/mytools.py math add --a 2 --b 3 --json
```

詳細規格與限制見 [docs/cli-export.md](docs/cli-export.md)。

## 架構定位

可以把 ToolAnything 想成四層：

1. Tool definition layer
2. Runtime layer
3. Transport layer
4. Developer tooling layer

這個分層的意義是：你寫的是工具與工具契約，不是一次又一次地重寫 protocol 與 integration plumbing。

如果你在意長期維護與擴充點，請直接看 [docs/architecture-walkthrough.md](docs/architecture-walkthrough.md)。

## 專案狀態

- 目前版本：`0.5.0`
- Python requirement：`>=3.10`
- 開發狀態：Beta

目前已具備：

- callable-first 與 source-based 兩條工具定義路徑
- MCP `stdio`、Streamable HTTP、legacy SSE/HTTP
- OpenAI tool schema adapter 與 tool loop runtime
- `doctor`、`inspect`、Claude Desktop integration
- examples、migration 文件與測試

這代表它已經適合拿來做原型、內部平台整合與架構驗證；若你要導入正式產品，建議先從自己的真實工具與 host 組合做一輪 smoke test。

## 文件索引

- [docs/docs-map.md](docs/docs-map.md)
- [docs/architecture-walkthrough.md](docs/architecture-walkthrough.md)
- [docs/migration-guide.md](docs/migration-guide.md)
- [docs/cli-export.md](docs/cli-export.md)
- [docs/mcp-test-client-spec.md](docs/mcp-test-client-spec.md)

## License

MIT
