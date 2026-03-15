# OpenAI Tool Calling

ToolAnything 不只會匯出 OpenAI tools schema，也提供 `OpenAIChatRuntime`，讓你可以直接對本地 registry 跑一個 Chat Completions 的工具呼叫迴圈。

## 這頁適合誰

- 你已經有 ToolAnything registry，想直接接 OpenAI tool calling
- 你不想自己手刻 tool schema、name mapping 與 tool result message
- 你想做本地 smoke test，而不是一開始就接完整 agent framework

## 前置條件

- 已安裝 ToolAnything
- 已設定 `OPENAI_API_KEY`
- 已在 registry 中註冊至少一支工具

## 最小範例

```python
from toolanything import OpenAIChatRuntime

runtime = OpenAIChatRuntime()
result = runtime.run(
    model="gpt-4.1-mini",
    prompt="請使用 weather.query 回答問題。",
)

print(result["final_text"])
```

## `OpenAIChatRuntime` 會幫你做什麼

- 把 registry 轉成 OpenAI `tools` payload
- 將 OpenAI-safe tool name 映回原始 registry 名稱
- 執行 tool call 並把結果轉成 tool message
- 迴圈呼叫 Chat Completions，直到模型回傳最終文字答案或超過輪數上限

## 重要方法

| 方法 | 用途 |
| --- | --- |
| `to_schema()` | 取得 OpenAI `tools` payload |
| `create_tool_call(...)` | 建立相容於 Chat Completions 的 tool_call |
| `invoke_tool_call(...)` | 執行單一 tool_call |
| `invoke_tool_calls(...)` | 依序執行一批 tool_call |
| `run(...)` / `run_async(...)` | 跑完整 tool loop |

## `run(...)` 的回傳內容

`run(...)` 會回傳一個 dict，常用欄位包含：

- `model`
- `tools_count`
- `final_text`
- `transcript`
- `messages`

其中 `transcript` 很適合拿來做除錯，因為它會保留 assistant message 與 tool invocation 的順序。

## 內建限制

- `model` 必須是非空字串
- `prompt` 必須是非空字串
- `max_rounds` 必須大於 `0`
- 若沒有明確傳入 `api_key`，會從 `OPENAI_API_KEY` 讀取
- 目前直接呼叫的是 Chat Completions API，並用 `tool_choice="auto"`

## 同步與非同步

- 在沒有事件迴圈時，用 `run(...)`、`execute_tool_call(...)`
- 在事件迴圈內，改用 `run_async(...)`、`invoke_tool_call(...)`

如果你在已運行的事件迴圈內呼叫同步方法，ToolAnything 會直接丟錯，要求改用 async 版本。

## 什麼時候不該用它

下列情境不建議把 `OpenAIChatRuntime` 當成完整答案：

- 你需要多 agent orchestration
- 你需要長期記憶、workflow、planning 框架
- 你要管理複雜的跨服務狀態機

它的定位是工具層 runtime，不是完整 agent platform。

## 相關文件

- [Tool Definition and Registration](Tool-Definition-and-Registration)
- [CLI Reference](CLI-Reference)
- [Architecture Walkthrough](Architecture-Walkthrough)
