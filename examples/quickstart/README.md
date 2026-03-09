# Quickstart（情境式入門）

這條路線的目標是：**從零跑通 MCP 流程**（工具定義 → 啟動 server → `tools/list` → CLI search → `tools/call`）。
你會先用最熟悉的 Python function + `@tool` 方式上手，跑通之後再去接 HTTP、SQL 或 model source 會比較容易。

> 下列步驟都在 repo 根目錄執行。

## 入口與關卡順序

1. **安裝/啟動/驗證清單**：`00_setup.md`
2. **定義工具**：`01_define_tools.py`
3. **啟動 transport**：`02_run_server.py`
4. **查詢與呼叫**：`03_search_and_call.py`

## 建議步驟

1. 依序完成 `00_setup.md` 的安裝與環境確認。
2. 執行 `01_define_tools.py`，確保工具註冊可以被 CLI 搜尋到。
3. 依照 `02_run_server.py` 啟動 MCP server。
   這個 quickstart 先用 `stdio`，因為它是本機測試最直接的路徑。
4. 參考 `03_search_and_call.py`，完成 `tools/list`、`toolanything search` 與 `tools/call`。

## 預期輸出（節錄）

- `toolanything search` 會回傳 JSON 列表，包含 `name`、`description`、`cost`、`latency_hint_ms`、`side_effect` 等欄位。
- `tools/list` 會列出剛註冊的工具名稱與 schema。
- `tools/call` 回傳工具執行結果，例如 `{ "city": "Taipei", "temp": 25 }`。

## 這條路線結束後你能做到

- 自己定義工具並帶 metadata（含 side_effect）。
- 用 CLI 搜尋工具。
- 透過 MCP `tools/list` 與 `tools/call` 驗證工具可用。
- 看懂最基本的「tool 定義 → registry/runtime → transport」資料流。

## 進階延伸（完成 Quickstart 後再看）

- `examples/demo_mcp_stdio.py`：最小 MCP stdio demo。
- `examples/streamable_http/`：用 3 支小範例看懂新版 `/mcp` transport 的 handshake、response mode 與 session lifecycle。
- `examples/demo_mcp_streamable_http.py`：最小 Streamable HTTP server demo。
- `examples/http_tool.py`：把 HTTP API 直接註冊成 tool，不再手寫 wrapper function。
- `examples/sql_tool.py`：把參數化 SQL 查詢直接註冊成 tool。
- `examples/onnx_tool.py`：看 VAD 前置門控如何用 ONNX model tool 表達。
- `examples/pytorch_tool.py`：看 VAD 前置門控如何用 PyTorch model tool 表達。
- `examples/protocol_boundary/`：看 MCP runtime 與 transport 的分工。
- `examples/opencv_mcp_web/`：較完整的 Web 範例。

如果你準備讓其他服務透過網路呼叫 MCP server，請先跑 `examples/streamable_http/`，再決定你的 client 要吃 JSON 還是 stream；SSE 屬於相容舊 client 的 legacy 路徑。
