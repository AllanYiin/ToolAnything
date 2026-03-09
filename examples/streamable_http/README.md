# Streamable HTTP Lab

這一組範例不是只教你「怎麼啟 server」，而是帶你**親手看懂 `/mcp` transport 的節奏**。
故事線會固定圍繞一個真實得多的情境：**VAD 先判斷一段音訊要不要送往 ASR**。
你會從最小 initialize 開始，一路走到 VAD gate、ASR preview、回應模式切換、`GET /mcp` stream、`Last-Event-ID` 與 `DELETE /mcp`。

這組範例的設計原則很簡單：

1. 每支腳本都自帶一個暫時的 demo server，不需要你先開第二個 terminal。
2. 每一步只多教一個 transport 概念，避免一下子把 session、SSE、JSON-RPC 全混在一起。
3. 輸出一律用 JSON，讓你可以直接對照 header、body、event。

## 建議順序

1. `python examples/streamable_http/01_handshake_and_list.py`
2. `python examples/streamable_http/02_response_modes.py`
3. `python examples/streamable_http/03_resume_and_close.py`

## 你會學到什麼

### 1. `01_handshake_and_list.py`

目標：
先把 **session 是怎麼建立的** 看清楚，並理解同一個 session 如何串起 VAD 與 ASR。

你會看到：

- `POST /mcp` 的 `initialize`
- 回傳的 `Mcp-Session-Id`
- 回傳的 `MCP-Protocol-Version`
- 接著如何用同一個 session 做 `tools/list`
- 先呼叫 `audio.vad.inspect_chunk`
- 再根據 VAD 結果決定要不要呼叫 `audio.asr.preview_transcript`

如果你想知道「Streamable HTTP 在實際音訊流程裡到底怎麼串接工具」，這支是最好的起點。

### 2. `02_response_modes.py`

目標：
理解 **VAD 之後的 ASR preview call 可以有不同回應模式**。

你會看到：

- 先用 JSON 模式拿到 VAD gate 結果
- `Accept: application/json` 時，ASR preview 直接回 JSON
- `Accept: text/event-stream` 時，ASR preview 以 SSE 事件回 `message` 與 `done`

這支範例適合你準備自己寫 client 時先跑一次。你會更清楚該怎麼在「先判斷、再送 ASR」的流程裡決定 client 要收 JSON 還是 stream。

### 3. `03_resume_and_close.py`

目標：
理解 **session lifecycle**，也就是 VAD/ASR client 連上、重連、關閉的完整故事。

你會看到：

- `GET /mcp` 接上 server-to-client stream
- 第一次連線收到 `ready` event
- 帶 `Last-Event-ID` 重連時，不會把舊事件重播一遍
- `DELETE /mcp` 後，原本 session 失效

這支範例是整組裡最接近真實遠端整合問題的一支。如果你正在寫自己的 MCP client，這支最值得反覆看。

## 想換成你自己的工具時怎麼做

這組 lab 為了讓你直接執行，內建了一個小型 demo registry，其中包含：

- `audio.vad.inspect_chunk`
- `audio.asr.preview_transcript`
- `audio.pipeline.status`

當你準備接自己的工具時，請改成正式入口：

```bash
toolanything serve your_module --streamable-http --port 9092
```

然後把 client 端目標改成：

```text
http://127.0.0.1:9092/mcp
```

## 延伸玩法

- 先跑這組 lab，再去看 `examples/protocol_boundary/README.md`，你會更容易看懂 transport 和 runtime 的分工。
- 如果你要比較新舊 transport 的差異，可以再看 `examples/demo_mcp.py`。那個是 legacy HTTP/SSE 路線，不是新的主路徑。
- 如果你想直接啟一個最小的 modern server，而不是自帶 demo server 的 lab，請看 `examples/demo_mcp_streamable_http.py`。
- 如果你想看真正的 model tool 版 VAD，請接著跑 `examples/pytorch_tool.py` 與 `examples/onnx_tool.py`。
