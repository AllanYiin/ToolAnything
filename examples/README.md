# Examples 總覽與編排邏輯

此目錄整理了各種 **ToolAnything / MCP** 範例，分成「情境式學習路線」與「單點功能示範」。
若你剛接觸本專案，建議依照學習路線循序完成；若你已知道要看的功能，可直接跳到對應示範。

## 編排邏輯

1. **情境式學習路線**：
   以「從零到一」為主線，逐步學習工具定義、傳輸、搜尋與策略化選擇。
2. **單點功能示範**：
   聚焦單一功能或技術面向（例如 stdio transport、HTTP server、特定工具模組）。

## 情境式學習路線（建議從上到下）

1. **Quickstart** — `examples/quickstart/`  
   最小可跑流程：定義工具 → 啟動 server → `tools/list` → CLI search → `tools/call`。
2. **Tool Selection** — `examples/tool_selection/`  
   展示 metadata / constraints / strategy 如何影響工具搜尋與排序。
3. **Protocol Boundary** — `examples/protocol_boundary/`  
   釐清 protocol/core 與 server/transport 的邊界與責任分工。

## 單點功能示範

- `examples/demo_mcp.py`：最小 MCP HTTP server demo。
- `examples/demo_mcp_stdio.py`：最小 MCP stdio demo。
- `examples/mcp_server_demo/`：簡單 client/server 對接示範。
- `examples/weather_tool/`：天氣工具模組範例。
- `examples/finance_tools/pipeline_demo.py`：金融工具管線示範。
- `examples/opencv_mcp_web/`：OpenCV MCP Web（ASGI/SSE）範例。

## 使用建議

- **第一次接觸**：照「情境式學習路線」往下跑，能最快理解完整流程。
- **已知需求**：直接看「單點功能示範」中的對應主題。
