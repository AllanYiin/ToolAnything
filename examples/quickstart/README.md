# Quickstart（情境式入門）

這條路線的目標是：**從零跑通 MCP 流程**（工具定義 → 啟動 server → `tools/list` → CLI search → `tools/call`）。

> 下列步驟都在 repo 根目錄執行。

## 入口與關卡順序

1. **安裝/啟動/驗證清單**：`00_setup.md`
2. **定義工具**：`01_define_tools.py`
3. **啟動 transport**：`02_run_server.py`
4. **查詢與呼叫**：`03_search_and_call.py`

## 這條路線結束後你能做到

- 自己定義工具並帶 metadata（含 side_effect）。
- 用 CLI 搜尋工具。
- 透過 MCP `tools/list` 與 `tools/call` 驗證工具可用。

## 進階延伸（完成 Quickstart 後再看）

- `examples/demo_mcp.py`：最小 MCP HTTP server demo。
- `examples/demo_mcp_stdio.py`：最小 MCP stdio demo。
- `examples/weather_tool/`：天氣工具模組。
- `examples/opencv_mcp_web/`：ASGI SSE 的完整範例。
