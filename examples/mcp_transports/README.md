# MCP Transports 比較與開發指南

ToolAnything 目前提供三種常見的 MCP transport：

- Streamable HTTP：新版 `/mcp`（建議優先使用）
- Legacy SSE：`GET /sse` + `POST /messages/{session_id}`（相容既有 client）
- Stdio：stdin/stdout（適合 Desktop 類 host 用 subprocess 啟動）

下面用「何時用」「怎麼開發」「怎麼驗證」三個角度，讓你可以快速選擇並落地。

## 一句話選擇

- 你要做「遠端/網路型整合」：用 Streamable HTTP。
- 你要接「Desktop host（Claude Desktop 類）」：用 stdio。
- 你要維持「舊 client 已經寫死 SSE 流程」：用 legacy SSE。

## 差異總覽

| Transport | 典型用途 | 優點 | 代價 / 注意事項 |
| --- | --- | --- | --- |
| Streamable HTTP (`/mcp`) | 任何 HTTP client、Web、服務間整合 | session lifecycle 清楚；可用 `POST /mcp` 走 JSON 或 event-stream；也支援 `GET /mcp` 重連 | 需要先 `initialize` 建 session，後續要帶 `Mcp-Session-Id` 與 `MCP-Protocol-Version` |
| Legacy SSE (`/sse` + `/messages/...`) | 舊版或既有 SSE client | 好相容、流程簡單 | 新整合不建議從這條開始；容易在 proxy/中介層遇到 SSE 緩衝問題 |
| Stdio (stdin/stdout) | Desktop host 啟動本機工具 | 最少網路設定；不需要 CORS | 你必須能用 subprocess 啟動 server；不適合多租戶/遠端 HTTP 網關 |

## 開發：先寫工具，再選 transport

不論你用哪個 transport，你都先定義工具（`@tool`）並確保 `tools/list`、`tools/call` 正常。

### 1. 寫一個最小工具模組

可以參考：

- `examples/quickstart/tools.py`
- `examples/opencv_mcp_web/server.py`

### 2. 用 CLI 啟動對應 transport

#### Streamable HTTP（建議）

```bash
toolanything serve your_module.py --streamable-http --host 127.0.0.1 --port 9092
```

MCP 端點是 `http://127.0.0.1:9092/mcp`。

#### Legacy SSE（相容用途）

```bash
toolanything serve your_module.py --legacy-http --host 127.0.0.1 --port 9090
```

此模式會暴露 `/sse` 與 `/messages/{session_id}`。

#### Stdio（Desktop host）

```bash
toolanything serve your_module.py --stdio
```

## 驗證：doctor 與 inspect

### Streamable HTTP/Legacy SSE（HTTP 模式）

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
toolanything inspect
```

`inspect` 裡選 `mode=http`、填 base url（不需要手動加 `/mcp`），ToolAnything 會優先用 Streamable HTTP，必要時才 fallback legacy。

### Stdio

```bash
toolanything doctor --mode stdio --cmd "python -m toolanything.cli serve your_module.py --stdio"
```

## 自己寫 client 時，三種 transport 的「最小握手」

### Streamable HTTP

1. `POST /mcp` 送 `initialize`（帶 `params.protocolVersion`）。
2. 從 response headers 拿到 `Mcp-Session-Id` 與 `MCP-Protocol-Version`。
3. 後續每次 `POST /mcp` 都帶上兩個 header，呼叫 `tools/list`、`tools/call`。
4. 需要 server-to-client stream 時，`GET /mcp`（帶 `Mcp-Session-Id`，並可用 `Last-Event-ID` 恢復）。
5. 不用時 `DELETE /mcp` 關閉 session。

### Legacy SSE

1. `GET /sse` 建立 SSE 連線，接收第一筆 message，取得可用的 `messages` endpoint（含 session_id）。
2. `POST /messages/{session_id}` 送 JSON-RPC payload（`initialize`、`tools/list`、`tools/call`）。
3. response 會以 SSE event 回推（通常是 `message` / `done`）。

### Stdio

1. 用 subprocess 啟動 server。
2. 將 JSON-RPC request 逐行寫入 stdin。
3. 從 stdout 逐行讀回 JSON-RPC response。

## Web/CORS 提醒（HTTP transports）

如果你的 Web UI 跟 MCP server 不同 origin，需要設定：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
```
