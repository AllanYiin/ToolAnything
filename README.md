# ToolAnything

> 把 Python function、class method、HTTP API、SQL query 或 model inference 變成可重用的 MCP / OpenAI tool。

ToolAnything 是一個 Python 工具層，目標是幫你把「工具定義、schema 產生、MCP server、OpenAI tool calling、CLI、診斷驗證」收斂到同一套 runtime。你不用先成為 MCP 專家，也不用為同一支工具維護兩套 schema。

如果你第一次聽到 ToolAnything，可以先把它想成：

1. 你用 Python 描述一支工具。
2. ToolAnything 把它轉成 MCP host 能發現與呼叫的 tool。
3. 同一份工具契約也可以輸出成 OpenAI tool schema、CLI command，並用本機工具驗證。

ToolAnything 不是完整 agent framework。它不負責 memory、planning、workflow orchestration 或產品 UI；它專注處理 agent / assistant 要安全、穩定呼叫外部工具時最容易重複造輪子的那一層。

這次特別值得注意的重點是「基礎工具集」：ToolAnything 內建一組可直接註冊的 standard tools，涵蓋網頁讀取、檔案讀取與資料轉換等常見 agent 工具需求，並保留 metadata、policy 與 opt-in 寫入防線。

## 適合誰

適合：

- 想把既有 Python function 或 class method 變成 MCP / OpenAI tools 的開發者。
- 正在做 agent、assistant、copilot、內部 AI 平台，需要可重用工具層的團隊。
- 已經有 HTTP API、SQL query、PyTorch / ONNX model，想直接接進 toolchain 的平台工程師。
- 需要 `doctor`、`inspect`、CLI export、Claude Desktop integration 這類本機驗證與整合工具的人。

不適合：

- 只想做一次性 demo，且只需要單一 MCP-only Python function。
- 想找完整 agent orchestration / memory / workflow 平台。
- 不打算使用 Python runtime。

## 你會得到什麼

| 能力 | 對新手開發者的意義 |
| --- | --- |
| 基礎工具集 | 直接註冊 `standard.web.fetch`、`standard.fs.read`、`standard.data.json_parse` 等常用工具，不用每個 agent 專案都重寫 |
| `@tool(...)` decorator | 用最少程式碼把穩定的 Python callable 變成 tool |
| source-based API | HTTP、SQL、model source 不必再多包一層薄 wrapper |
| MCP server | 用 `stdio`、Streamable HTTP 或 legacy SSE/HTTP 暴露工具 |
| OpenAI adapter / runtime | 同一份工具契約可轉成 OpenAI tool schema，也可跑 tool loop |
| `doctor` | 檢查 initialize、`tools/list`、`tools/call` 是否真的可用 |
| `inspect` | 用 Web 介面看 schema、送 tool call、檢查 MCP transcript |
| CLI export | 把同一份 ToolContract 輸出成命令列工具，方便人工 smoke test 或 CI |

## 這次重點：基礎工具集

很多 agent 專案一開始都會重寫同一批工具：讀檔、搜尋文字、解析 JSON、抓網頁、整理 HTML 文字、做簡單資料轉換。ToolAnything 的基礎工具集把這些能力做成可註冊、可匯出、可治理的 standard tools。

目前重點能力：

| 工具 | 預設狀態 | 能做什麼 | 安全邊界 |
| --- | --- | --- | --- |
| `standard.fs.list` | 預設註冊 | 列出指定 root 內的目錄項目 | root-scoped；只能碰 `StandardToolRoot` 允許的路徑 |
| `standard.fs.stat` | 預設註冊 | 查詢指定路徑的 metadata | root-scoped；不讀取檔案內容 |
| `standard.fs.search` | 預設註冊 | 在指定 root 內搜尋文字內容 | root-scoped；受 ignored dirs、掃描檔案數與 timeout 限制 |
| `standard.fs.read` | 預設註冊 | 讀取 root 內文字檔 | root-scoped；受檔案大小與讀取字元數限制 |
| `standard.fs.write` | opt-in 寫入 | 建立檔案，或在提供 `expected_sha256` 時覆寫檔案 | 必須 `include_write_tools=True` 且 root 標成 writable |
| `standard.fs.replace_if_match` | opt-in 寫入 | 比對目前 SHA-256 後替換整個檔案 | 必須 writable root；SHA-256 不符就拒絕寫入 |
| `standard.fs.patch_text` | opt-in 寫入 | 對文字檔做 search/replace 類 patch，可先 preview | 必須 writable root；套用時需要目前 SHA-256 guard |
| `standard.fs.apply_unified_patch` | opt-in 寫入 | 套用單一目標檔案的 unified diff | 必須 writable root；限制單檔 patch，避免跨檔大範圍修改 |
| `standard.web.fetch` | 預設註冊 | 讀取 HTTP(S) 文字型資源 | 讀取導向；受 domain、content-type、timeout、redirect policy 限制 |
| `standard.web.extract_text` | 預設註冊 | 從 HTML 抽取主要文字 | 過濾常見非內容區塊；不執行互動式瀏覽器操作 |
| `standard.web.extract_links` | 預設註冊 | 從 HTML 抽取連結 | 只解析輸入內容，不提交表單或下載檔案 |
| `standard.web.search` | 預設註冊 | 透過 host/provider 執行搜尋 | 可接自訂 `search_provider`；provider 行為由 host 控制 |
| `standard.data.json_parse` | 預設註冊 | 解析 JSON 文字 | 受 `max_read_chars` 限制 |
| `standard.data.json_validate` | 預設註冊 | 用小型 JSON Schema subset 驗證 JSON | 有 `jsonschema` 時使用較強驗證；否則走 dependency-free fallback |
| `standard.data.jsonl_inspect` | 預設註冊 | 檢查 JSONL 結構與樣本 | 受讀取大小與樣本數限制 |
| `standard.data.csv_inspect` | 預設註冊 | 檢查 CSV 欄位、列數與樣本 | 受讀取大小與樣本數限制 |
| `standard.data.xml_inspect` | 預設註冊 | 檢查 XML 結構摘要 | 拒絕 DTD，降低 XML 外部實體風險 |
| `standard.data.toml_parse` | 預設註冊 | 解析 TOML 文字 | 受 `max_read_chars` 限制 |
| `standard.data.yaml_parse` | 預設註冊 | 解析 YAML 文字 | 使用安全解析路徑；受 `max_read_chars` 限制 |
| `standard.data.markdown_extract_links` | 預設註冊 | 從 Markdown 文字抽取連結 | 只解析文字，不讀取或下載連結目標 |
| `standard.browser.extract_text` | opt-in browser | 透過 host 的唯讀 browser provider 抽頁面文字 | 必須 `include_browser_tools=True` 且提供 `browser_readonly_provider` |
| `standard.browser.snapshot` | opt-in browser | 透過 host 的唯讀 browser provider 取得頁面快照 | 唯讀 provider；不負責表單提交或下載寫入 |

最小註冊方式：

```python
from pathlib import Path
from toolanything import ToolRegistry, register_standard_tools
from toolanything.standard_tools import StandardToolOptions, StandardToolRoot

registry = ToolRegistry()
register_standard_tools(
    registry,
    StandardToolOptions(
        roots=(StandardToolRoot("workspace", Path.cwd()),),
    ),
)
```

寫入工具必須顯式 opt-in，例如設定 `include_write_tools=True` 並提供 writable root。這個設計是刻意的：基礎工具集要能被 agent 重用，但不能把讀取工具和高風險寫入混在同一個預設安全等級裡。

完整範例見 [examples/standard_tools](examples/standard_tools/README.md)，參考文件見 [docs/standard-tools.md](docs/standard-tools.md)。

## 安裝

需求：

- Python `>=3.10`

一般使用者安裝：

```bash
pip install toolanything
```

如果你是在這個 repo 裡開發 ToolAnything 本身：

```bash
git clone <this-repo>
cd ToolAnything
pip install -e .[dev]
```

`.[dev]` 會安裝測試、文件與 model tool 相關依賴，例如 `pytest`、`httpx`、`onnx`、`onnxruntime`、`mkdocs`。

## 5 分鐘快速開始

這段會從零建立一支 `calculator.add` 工具，啟動成 MCP Streamable HTTP server，然後用 `doctor` 驗證它真的能被發現與呼叫。

### 1. 建立工具檔案

建立 `tools.py`：

```python
from toolanything import tool


@tool(name="calculator.add", description="加總兩個整數")
def add(a: int, b: int) -> int:
    return a + b
```

`@tool(...)` 會把函數名稱、描述、型別註記與參數轉成工具契約。穩定的 Python function 或 class method，優先用這條路徑。

### 2. 啟動 MCP server

```bash
toolanything serve tools.py --streamable-http --host 127.0.0.1 --port 9092
```

新的 HTTP 型 MCP 整合建議先用 Streamable HTTP。若你要接 Claude Desktop 這類會啟動本機子程序的 host，才改用 `stdio`：

```bash
toolanything serve tools.py --stdio
```

### 3. 在另一個終端機驗證

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
```

成功時，你應該會看到 server 初始化、列出工具、呼叫工具的檢查結果。這一步很重要，因為 README 範例不是只產生 schema，而是確認 host 真能透過 MCP 呼叫工具。

如果你要驗證 `stdio`：

```bash
toolanything doctor --mode stdio --tools tools
```

### 4. 開啟互動式 inspector

```bash
toolanything inspect
```

`inspect` 適合用來看：

- MCP tool schema
- `tools/list` 與 `tools/call` transcript
- 手動送出的 tool arguments
- OpenAI tool-calling smoke test

## 下一步該選哪條路

| 你的來源 | 建議用法 | 先看範例 |
| --- | --- | --- |
| 一般 Python function | `@tool(...)` | [examples/quickstart](examples/quickstart/README.md) |
| class method | `@tool(...)`，兩種 decorator 順序都支援 | [examples/class_method_tools](examples/class_method_tools/README.md) |
| HTTP API | `register_http_tool(...)` 或 HTTP source spec | [examples/non_function_tools/http_tool.py](examples/non_function_tools/http_tool.py) |
| SQL query | `register_sql_tool(...)` 或 SQL source spec | [examples/non_function_tools/sql_tool.py](examples/non_function_tools/sql_tool.py) |
| ONNX / PyTorch model | `register_model_tool(...)` 或 model source spec | [examples/non_function_tools](examples/non_function_tools/README.md) |
| 一組可搜尋工具 | metadata + search strategy | [examples/tool_selection](examples/tool_selection/README.md) |
| 基礎工具集 / standard tools | 直接註冊常用 web、filesystem、data tools | [examples/standard_tools](examples/standard_tools/README.md) |

判斷原則很簡單：

- 穩定的 Python callable 或 class method：先用 `@tool(...)`。
- 真正來源是 HTTP、SQL 或 model：優先用 source-based API，不要為了接工具而再手寫一層薄 wrapper。
- 要讓 agent 長期重用：啟動 server 後一定跑 `doctor` 或 `inspect`。

## OpenAI tool calling

ToolAnything 可以把 registry 內的工具轉成 OpenAI tool schema，並處理 tool name mapping 與本地呼叫。

最小用法：

```python
from toolanything import OpenAIChatRuntime

runtime = OpenAIChatRuntime()
result = runtime.run(
    model="gpt-4.1-mini",
    prompt="請使用 calculator.add 計算 2 + 3。",
)

print(result["final_text"])
```

預設會從 `OPENAI_API_KEY` 讀取 API key。若你只想先確認 OpenAI schema，不需要立刻打真實 API，可以先使用 `doctor`、`inspect` 或 adapter 相關測試範例。

## MCP transport 怎麼選

| Transport | 適合情境 |
| --- | --- |
| `stdio` | Claude Desktop、IDE、本機 agent host 直接啟動 server 子程序 |
| Streamable HTTP | 新版 MCP HTTP 整合、服務間連線、本機或遠端 server |
| legacy SSE / HTTP | 相容舊 client，除非需要相容性，不建議新整合優先選它 |

新的 HTTP 整合預設先選 Streamable HTTP。若在本機開 server，建議綁定 `127.0.0.1`，不要直接暴露到 `0.0.0.0`，除非你已經處理 Origin、認證、權限與網路邊界。

## 常見工作流

### 把工具接到 Claude Desktop

產生設定片段：

```bash
toolanything init-claude --module examples/opencv_mcp_web/server.py --port 9090
```

直接寫入設定檔：

```bash
toolanything install-claude --module examples/opencv_mcp_web/server.py --port 9090
```

### 把同一份工具變成 CLI

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools
toolanything cli run --config toolanything.cli.json -- math add --a 2 --b 3 --json
```

如果你想輸出可直接執行的 launcher：

```bash
toolanything cli export --module tests.fixtures.sample_tools --app-name mytools --launcher .toolanything/mytools.py
python .toolanything/mytools.py math add --a 2 --b 3 --json
```

詳細規格見 [docs/cli-export.md](docs/cli-export.md)。

### 使用 source-based tools

如果你要接的不是 Python callable，而是外部系統，請先看：

- [HTTP source example](examples/non_function_tools/http_tool.py)
- [SQL source example](examples/non_function_tools/sql_tool.py)
- [ONNX model example](examples/non_function_tools/onnx_tool.py)
- [PyTorch model example](examples/non_function_tools/pytorch_tool.py)
- [Migration Guide](docs/migration-guide.md)

## 專案導覽

第一次進 repo，建議照這個順序：

| 想解決的問題 | 先看哪裡 |
| --- | --- |
| 從零跑通最小流程 | [examples/quickstart/README.md](examples/quickstart/README.md) |
| 理解範例路線 | [examples/README.md](examples/README.md) |
| 理解 transport 差異 | [examples/mcp_transports/README.md](examples/mcp_transports/README.md) |
| 做 Streamable HTTP 整合 | [examples/streamable_http/README.md](examples/streamable_http/README.md) |
| 把 HTTP / SQL / model 變成 tool | [examples/non_function_tools/README.md](examples/non_function_tools/README.md) |
| 做工具搜尋與選擇策略 | [examples/tool_selection/README.md](examples/tool_selection/README.md) |
| 理解架構與擴充點 | [docs/architecture-walkthrough.md](docs/architecture-walkthrough.md) |
| 從舊寫法遷移 | [docs/migration-guide.md](docs/migration-guide.md) |
| 找完整文件地圖 | [docs/docs-map.md](docs/docs-map.md) |

## 重要概念

### MCP tools

MCP tool 是 server 暴露給 client / host 的可呼叫能力。host 會透過 `tools/list` 發現工具，再透過 `tools/call` 傳入 arguments 並取得結果。ToolAnything 的 `serve` 與 `doctor` 就是在幫你把這條路徑本機化、可驗證化。

官方規格參考：[MCP Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)、[MCP Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)。

### OpenAI tool calling

OpenAI tool calling 讓模型根據你提供的工具 schema 決定是否呼叫工具。工具 schema 以 JSON Schema 描述參數；若使用 strict mode，schema 需要滿足更嚴格的結構要求。ToolAnything 的價值是讓你不用為 MCP 與 OpenAI 各維護一套工具描述。

官方文件參考：[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)。

### Tool metadata 與治理

當工具變多，光有 `name` 與 `description` 不夠。ToolAnything 支援 metadata、search strategy、policy 與 governance metadata，讓你能表達成本、延遲、副作用、權限、用途限制等資訊。相關文件：

- [docs/standard-tools.md](docs/standard-tools.md)
- [docs/tool-metadata-governance-spec.md](docs/tool-metadata-governance-spec.md)

## 開發與驗證

常用檢查：

```bash
pytest
```

建文件：

```bash
python scripts/generate_api_docs.py
mkdocs build
```

如果你改了 CLI、runtime、transport、adapter 或 metadata，至少要補一個能證明行為的測試，並跑對應測試檔。不要只靠 README 範例判斷功能正確。

## 專案狀態

- 目前版本：`0.6.0`
- Python requirement：`>=3.10`
- 開發狀態：Beta

已具備：

- callable-first 與 source-based 兩條工具定義路徑
- MCP `stdio`、Streamable HTTP、legacy SSE/HTTP
- OpenAI tool schema adapter 與 tool loop runtime
- `doctor`、`inspect`、Claude Desktop integration
- CLI export
- 基礎工具集 / standard tools、metadata、policy 與 governance metadata
- examples、migration 文件與測試

正式導入產品前，建議用自己的真實工具與 host 組合跑一輪 smoke test：先 `serve`，再 `doctor`，最後用實際 host 或 `inspect` 呼叫。

## License

MIT
