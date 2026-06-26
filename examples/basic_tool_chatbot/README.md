# Basic tool chatbot example

這個範例示範如何把 ToolAnything 的基礎工具集接到一個簡單 chatbot
對話介面。預設模式不需要 `OPENAI_API_KEY`：server 會使用
`OpenAIChatRuntime` 搭配一個 deterministic requester，走完整的
OpenAI-style tool loop，讓你可以看到模型訊息、tool call、tool result
與最後回覆如何串起來。

## 執行

請在 repo root 執行：

```bash
python examples/basic_tool_chatbot/server.py
```

瀏覽器開啟：

```text
http://127.0.0.1:5174
```

也可以用一次性 smoke 模式確認 server 端流程：

```bash
python examples/basic_tool_chatbot/server.py --once "讀取 notes/intro.txt"
python examples/basic_tool_chatbot/server.py --once '解析 JSON {"city":"Taipei","count":2}'
python examples/basic_tool_chatbot/server.py --once "搜尋 ToolAnything standard tools"
```

## 範例內容

- `server.py`：建立 demo workspace、註冊 standard tools、提供 `/api/chat`。
- `web/index.html`：chatbot 對話介面。
- `web/app.js`：送出訊息、顯示 assistant 回覆與工具 transcript。
- `web/styles.css`：介面樣式。

## 重要邊界

- 這是介面與 tool loop 範例，不是真正的 LLM 評估器。
- 預設只註冊唯讀 standard tools；寫入工具沒有啟用。
- `standard.web.search` 使用範例內建 provider，不會連到真實搜尋服務。
- 若要接真實 OpenAI API，可把 `runtime.run(..., requester=...)` 改成不傳
  requester，並提供 `OPENAI_API_KEY` 與 model。
