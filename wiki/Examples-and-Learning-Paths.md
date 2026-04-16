# Examples and Learning Paths

這一頁把 `examples/` 目錄整理成幾條學習與驗證路線，避免第一次進 repo 就被資料夾數量淹沒。

## 建議順序

| 路線 | 先看哪裡 | 你會學到什麼 |
| --- | --- | --- |
| 最短上手 | `examples/quickstart/` | 用 `@tool` 跑通定義、啟動、搜尋與呼叫 |
| class method | `examples/class_method_tools/` | `@tool` 與 `@classmethod` 的兩種疊法 |
| 新版 MCP HTTP | `examples/streamable_http/` | `/mcp` handshake、response mode、resume / close |
| 標準工具集 | `examples/standard_tools/` | 註冊內建 web / filesystem / data tools，並輸出 OpenAI / MCP / CLI metadata |
| source-based tools | `examples/non_function_tools/` | HTTP / SQL / ONNX / PyTorch 直接註冊成 tool |
| 工具搜尋策略 | `examples/tool_selection/` | metadata、constraints、strategy 如何影響排序 |
| 協議邊界 | `examples/protocol_boundary/` | protocol、runtime、transport 的責任分工 |

## 路線 1：第一次用 ToolAnything

建議順序：

1. `examples/quickstart/README.md`
2. `toolanything doctor --mode http --url http://127.0.0.1:9092`
3. `toolanything inspect`

目標：

- 跑通第一支工具
- 看懂 `tools/list` 與 `tools/call`
- 知道 CLI 與 Web inspector 怎麼驗證

## 路線 2：我要自己寫 MCP client

建議順序：

1. `examples/streamable_http/README.md`
2. `examples/mcp_transports/README.md`
3. `examples/protocol_boundary/README.md`

目標：

- 理解 `/mcp` session lifecycle
- 知道什麼時候該用 Streamable HTTP、stdio 或 legacy SSE
- 釐清 transport 與 protocol core 的分工

## 路線 3：我要把外部系統直接接成 tool

建議順序：

1. `examples/non_function_tools/http_tool.py`
2. `examples/non_function_tools/sql_tool.py`
3. `examples/non_function_tools/onnx_tool.py`
4. `examples/non_function_tools/pytorch_tool.py`

目標：

- 了解 source-based API 的心智模型
- 避免為 REST API、SQL 或模型硬寫一層 wrapper function
- 知道 SQL / model 工具各自需要哪些額外依賴

## 路線 4：我要使用內建標準工具集

建議順序：

1. `examples/standard_tools/README.md`
2. `python examples/standard_tools/01_register_and_export.py`
3. `python examples/standard_tools/02_write_tools_opt_in.py`
4. `python examples/standard_tools/03_provider_search.py`

目標：

- 知道標準工具集本體在 `src/toolanything/standard_tools/`，不是 `examples/`
- 看懂 `to_openai()`、`to_mcp()`、`to_cli()` 的輸出差異
- 知道寫入工具與 provider-backed search 都是 host 明確 opt-in

## 路線 5：我要把工具搜尋做得更像平台能力

看：

- `examples/tool_selection/README.md`
- `python examples/tool_selection/03_custom_strategy.py`

目標：

- 理解 tags、cost、latency、side effect、category 等欄位的價值
- 知道如何用自訂策略接進 `ToolSearchTool`

## 路線 6：我要看較完整的 Web 範例

看：

- `examples/opencv_mcp_web/README.md`

這條路線比 Quickstart 更接近實際產品整合場景，但也比較重，不建議拿來當第一個範例。

## 依賴提醒

- HTTP / SQL 範例：基本安裝即可
- ONNX 範例：需要 `onnxruntime`
- 若要重建 ONNX artifact：需要 `onnx`
- PyTorch 範例：需要 `torch`

## 相關文件

- [Getting Started](Getting-Started)
- [Tool Definition and Registration](Tool-Definition-and-Registration)
- [MCP Serving and Transports](MCP-Serving-and-Transports)
- [Standard Tools](Standard-Tools)
