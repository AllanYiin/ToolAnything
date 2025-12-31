# Protocol Boundary（協議邊界與 transport 對照）

這條路線的目標是：**釐清 protocol/core 與 server/transport 的責任分界**，避免在錯誤的層級修改行為。

## 情境目標

- 了解 MCP JSON-RPC method routing 位於 protocol/core。
- 了解 HTTP / stdio transport 僅負責傳輸與依賴注入。
- 能判斷要在哪一層擴充功能（不改動核心 routing）。

## 建議步驟

1. 對照 `src/toolanything/protocol/mcp_jsonrpc.py` 的 `handle()` 與 method routing。
2. 對照 `src/toolanything/server/mcp_tool_server.py` 與 `src/toolanything/server/mcp_stdio_server.py`，確認 transport 如何轉交 request。
3. 參考 `docs/architecture-walkthrough.md`，確認協議邊界與擴充方式的文字描述。

## 預期輸出（節錄）

- 能清楚描述「protocol/core」與「server/transport」的分工。
- 能指出新增功能應該落在哪一層，而不會修改 routing。

## 延伸閱讀

- [`docs/architecture-walkthrough.md`](../../docs/architecture-walkthrough.md)
- [`src/toolanything/protocol/mcp_jsonrpc.py`](../../src/toolanything/protocol/mcp_jsonrpc.py)
- [`src/toolanything/server/mcp_tool_server.py`](../../src/toolanything/server/mcp_tool_server.py)
- [`src/toolanything/server/mcp_stdio_server.py`](../../src/toolanything/server/mcp_stdio_server.py)
