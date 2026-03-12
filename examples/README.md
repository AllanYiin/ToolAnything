# Examples 使用指南

這個目錄現在就是 repo 內唯一的範例來源，沒有另一份藏在 `src/` 裡的 package demo。

範例大致分成兩條路線：

1. 先學會怎麼把 Python function 註冊成 tool，並透過 MCP 呼叫。
2. 再進一步把 HTTP API、SQL 查詢、PyTorch/ONNX 模型直接註冊成 tool，不再手寫 wrapper function。

如果你是第一次接觸 ToolAnything，請先跑「情境式學習路線」；如果你已經知道自己要把哪種來源接進來，可以直接跳到對應範例。

## 建議學習順序

1. **Quickstart** — `examples/quickstart/`  
   從 `@tool` 開始，跑通最小流程：定義工具、啟動 server、`tools/list`、CLI search、`tools/call`。
2. **Streamable HTTP Lab** — `examples/streamable_http/`  
   用 3 支小範例看懂新版 `/mcp` transport：initialize、response mode、session resume/close。
3. **Source-based tools** — `examples/non_function_tools/`  
   把 HTTP API、SQL、ONNX、PyTorch 直接變成 tool，理解新的 source-based / invoker-first 設計。
4. **Tool Selection** — `examples/tool_selection/`  
   了解 metadata、constraints、strategy 如何影響搜尋與排序。
5. **Protocol Boundary** — `examples/protocol_boundary/`  
   了解 protocol、runtime、transport 的邊界，避免把功能改在錯誤層級。

## Source-based tools 範例

- `examples/non_function_tools/http_tool.py`：把 HTTP endpoint 宣告成 tool，示範 path/query schema 與執行流程。
- `examples/non_function_tools/sql_tool.py`：把參數化 SQL 查詢註冊成 tool，示範 connection provider、查詢結果格式，以及隨附的 SQLite 範例資料庫。
- `examples/non_function_tools/onnx_tool.py`：VAD 前置門控範例，示範 ONNX model artifact、tensor input schema 與 postprocessor。
- `examples/non_function_tools/pytorch_tool.py`：VAD 前置門控範例，示範 PyTorch model artifact、session cache 與 postprocessor。

這組 source-based 範例集中放在同一個資料夾，是刻意的：它們都屬於「非函數工具」示範，不應再拆成一部分在 `examples/`、另一部分在 `src/`。

執行這些範例前，請先確認你已安裝相依套件：

- HTTP / SQL 範例只需要基本安裝。
- ONNX 範例需要 `onnx` 與 `onnxruntime`。
- PyTorch 範例需要 `torch`。

## MCP transport 範例

- `examples/mcp_transports/README.md`：三種 transport（Streamable HTTP / legacy SSE / stdio）比較、用途與開發指南。
- `examples/demo_mcp_stdio.py`：最小 stdio 範例，適合本機 client 透過 subprocess 啟動。
- `examples/demo_mcp_streamable_http.py`：最小 Streamable HTTP server demo。
- `examples/streamable_http/`：由淺入深的 Streamable HTTP lab，適合你自己寫 client 或想看 raw request/response。
- `examples/demo_mcp.py`：傳統 HTTP/SSE server demo（legacy compatibility）。
- `examples/opencv_mcp_web/`：較完整的 Web 範例，示範外部檔案路徑工作流。

如果你要做新的遠端 MCP 整合，請優先使用 Streamable HTTP transport；舊的 SSE 路徑保留給相容既有 client 的情境。

## 其他範例

- `examples/mcp_server_demo/`：簡單 client/server 對接示範。
- `examples/weather_tool/`：模組化工具定義範例。
- `examples/finance_tools/pipeline_demo.py`：金融工具管線示範。

## 你可以怎麼選

- 想先理解最小工具流程：從 `examples/quickstart/` 開始。
- 想把新版 `/mcp` transport 看懂：先跑 `examples/streamable_http/`。
- 想把外部系統直接接成 tool：直接看 HTTP / SQL / model 範例。
- 想釐清 MCP transport 與 runtime 邊界：看 `examples/protocol_boundary/`。
