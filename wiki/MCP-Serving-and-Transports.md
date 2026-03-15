# MCP Serving and Transports

這一頁是任務型指南，回答的是：「我已經有工具了，接下來要怎麼把它提供給 MCP host？」

## 一句話選擇

- 要做 Desktop host 整合：用 `stdio`
- 要做新的網路型整合：用 Streamable HTTP
- 要維持舊 client 相容：用 legacy HTTP/SSE

## transport 比較

| Transport | 啟動方式 | 典型場景 | 注意事項 |
| --- | --- | --- | --- |
| `stdio` | `toolanything serve <module> --stdio` | Claude Desktop、IDE、本機 agent host | 需要用 subprocess 啟動 |
| Streamable HTTP | `toolanything serve <module> --streamable-http --port 9092` | 新版 MCP HTTP 整合、服務間連線 | 端點在 `/mcp`，需先 `initialize` 建 session |
| legacy HTTP/SSE | `toolanything serve <module>` | 舊 client 相容路徑 | 新整合不建議優先從這條開始 |

## 啟動方式

### Stdio

```bash
toolanything serve examples/quickstart/tools.py --stdio
```

### Streamable HTTP

```bash
toolanything serve examples/quickstart/tools.py --streamable-http --host 127.0.0.1 --port 9092
```

MCP 端點：

```text
http://127.0.0.1:9092/mcp
```

### Legacy HTTP/SSE

```bash
toolanything serve examples/quickstart/tools.py --host 127.0.0.1 --port 9090
```

這會啟動 legacy server。現有文件描述的端點包含 `/sse` 與 `/messages/{session_id}`。

## Streamable HTTP 最小握手

1. `POST /mcp` 送 `initialize`
2. 從 response headers 取得 `Mcp-Session-Id` 與 `MCP-Protocol-Version`
3. 後續呼叫 `tools/list`、`tools/call` 時都帶上這兩個 header
4. 需要 server-to-client stream 時，可用 `GET /mcp`
5. 不再使用時可 `DELETE /mcp` 關閉 session

如果你要自己寫 client，`examples/streamable_http/` 是最直接的參考。

## 驗證 transport

### 驗證 stdio

```bash
toolanything doctor --mode stdio --tools examples.quickstart.tools
```

### 驗證 HTTP

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
```

### 互動式檢查

```bash
toolanything inspect
```

`inspect` 的 HTTP 模式會優先走 Streamable HTTP，必要時再 fallback 到 legacy 路徑。

## Claude Desktop 整合

只產生設定片段：

```bash
toolanything init-claude --module examples/opencv_mcp_web/server.py --port 9090
```

直接寫入 Claude Desktop 設定：

```bash
toolanything install-claude --module examples/opencv_mcp_web/server.py --port 9090
```

## Web/CORS 提醒

如果你的 Web UI 與 MCP server 不同 origin，先設定允許來源：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
```

## 什麼時候該升級成 Streamable HTTP

下列情況建議直接用 Streamable HTTP，不要再從 legacy 路徑開始：

- 你的 client 是新寫的
- 你需要比較清楚的 session lifecycle
- 你要處理 `GET /mcp` stream、重連或 `Last-Event-ID`
- 你不想再承受 SSE 在 proxy 或中介層的緩衝問題

## 相關文件

- [Getting Started](Getting-Started)
- [Diagnostics and Troubleshooting](Diagnostics-and-Troubleshooting)
- [Examples and Learning Paths](Examples-and-Learning-Paths)
