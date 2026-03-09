# Protocol Boundary（協議邊界與 transport 對照）

這條路線的目標是：**釐清 protocol/core、runtime、transport 的責任分界**，避免在錯誤的層級修改行為。

## 情境目標

- 了解 MCP JSON-RPC method routing 位於 protocol/core。
- 了解 tool 執行發生在 runtime / invoker 層，而不是 transport 層。
- 了解 stdio、Streamable HTTP、legacy SSE 各自負責什麼。
- 能判斷要在哪一層擴充功能，而不是把需求硬塞進 server routing。

## 建議步驟

1. 先跑 `examples/streamable_http/01_handshake_and_list.py`，建立 `/mcp` session 與 headers 的直覺。
2. 再跑 `examples/streamable_http/02_response_modes.py`，看 `Accept` 如何改變 transport 行為。
3. 接著跑 `examples/streamable_http/03_resume_and_close.py`，理解 `GET /mcp`、`Last-Event-ID` 與 `DELETE /mcp`。
4. 對照 `src/toolanything/protocol/mcp_jsonrpc.py` 的 `handle()` 與 method routing。
5. 對照 `src/toolanything/server/mcp_runtime.py`，理解 request 進來之後如何分派到 runtime。
6. 對照 `src/toolanything/server/mcp_streamable_http.py` 與 `src/toolanything/server/mcp_stdio_server.py`，確認 transport 如何轉交 request。
7. 參考 `docs/architecture-walkthrough.md`，確認 source、contract、invoker、runtime、transport 的分層。

## 預期輸出（節錄）

- 能清楚描述「protocol/core」「runtime/invoker」「transport」的分工。
- 能判斷新功能是應該改 tool runtime、source compiler，還是只需要補 transport。
- 能說明為什麼新的遠端整合應該優先選 Streamable HTTP，而不是直接從 SSE 開始。

## transport 選擇建議

- 本機 subprocess 整合：先用 `stdio`。
- 新的遠端 HTTP 整合：優先用 Streamable HTTP。
- 只有既有 client 已經綁定 SSE 時：才使用 legacy SSE 相容路徑。

## 延伸閱讀

- [`examples/streamable_http/README.md`](../streamable_http/README.md)
- [`docs/architecture-walkthrough.md`](../../docs/architecture-walkthrough.md)
- [`src/toolanything/protocol/mcp_jsonrpc.py`](../../src/toolanything/protocol/mcp_jsonrpc.py)
- [`src/toolanything/server/mcp_runtime.py`](../../src/toolanything/server/mcp_runtime.py)
- [`src/toolanything/server/mcp_streamable_http.py`](../../src/toolanything/server/mcp_streamable_http.py)
- [`src/toolanything/server/mcp_stdio_server.py`](../../src/toolanything/server/mcp_stdio_server.py)
