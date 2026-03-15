# ToolAnything Wiki

ToolAnything 是一個給 LLM 應用開發者的 Python 工具層。你定義一次工具，就能同時接上 MCP 與 OpenAI tool calling，而不用自己維護兩套 schema、兩套路由與兩套執行迴圈。

這份 Wiki 的目標不是取代自動生成的 API reference，而是把最重要的上手路徑、協議整合方式、架構邊界、遷移重點與除錯方法整理成一組可維護的技術文件。

## 這個專案適合誰

- 想把 Python function 或 class method 暴露成 MCP / OpenAI tools 的開發者
- 需要同時支援 MCP 與 OpenAI tool calling 的產品團隊
- 想把 HTTP API、SQL 查詢或模型推論直接接成正式工具的整合工程師
- 想快速驗證 transport、`tools/list`、`tools/call`、工具搜尋與 OpenAI tool loop 的平台團隊

## 核心能力

| 能力 | 你得到的價值 |
| --- | --- |
| 一份工具同時支援 MCP 與 OpenAI | 降低雙協議維護成本，避免 schema drift |
| `@tool` 與 source-based API 並存 | 可從 callable 快速上手，也能直接接 HTTP / SQL / model |
| `toolanything serve` | 用同一套入口啟動 stdio、Streamable HTTP 或 legacy HTTP/SSE |
| `toolanything doctor` 與 `toolanything inspect` | 在本機驗證 transport、握手、`tools/list`、`tools/call` 與互動式測試 |
| `OpenAIChatRuntime` | 直接跑 Chat Completions 的工具呼叫迴圈 |
| metadata 與搜尋策略 | 工具變多後仍能做條件篩選與排序 |

## 快速閱讀路線

### 我只想先跑起來

1. 看 [Getting Started](Getting-Started)
2. 再看 [CLI Reference](CLI-Reference)
3. 驗證完成後看 [Examples and Learning Paths](Examples-and-Learning-Paths)

### 我要把 ToolAnything 接到 MCP host

1. 看 [Getting Started](Getting-Started)
2. 再看 [MCP Serving and Transports](MCP-Serving-and-Transports)
3. 需要除錯時看 [Diagnostics and Troubleshooting](Diagnostics-and-Troubleshooting)

### 我要理解設計與擴充點

1. 先看 [Architecture Walkthrough](Architecture-Walkthrough)
2. 再看 [Tool Definition and Registration](Tool-Definition-and-Registration)
3. 最後看 [Migration Guide](Migration-Guide)

## 專案狀態

- 版本：`0.1.0`
- Python requirement：`>=3.10`
- 開發狀態：Alpha
- 預設工作目錄：本文中的命令都假設你在 repo root 執行

## 文件地圖

- [Getting Started](Getting-Started)
- [Tool Definition and Registration](Tool-Definition-and-Registration)
- [MCP Serving and Transports](MCP-Serving-and-Transports)
- [OpenAI Tool Calling](OpenAI-Tool-Calling)
- [CLI Reference](CLI-Reference)
- [Examples and Learning Paths](Examples-and-Learning-Paths)
- [Architecture Walkthrough](Architecture-Walkthrough)
- [Migration Guide](Migration-Guide)
- [Diagnostics and Troubleshooting](Diagnostics-and-Troubleshooting)
- [Documentation and API Reference](Documentation-and-API-Reference)
- [Maintaining the Wiki](Maintaining-the-Wiki)

## 這份 Wiki 沒有做什麼

- 不手動複製整份 Python API reference；該部分仍由 `scripts/generate_api_docs.py` 從 `src/toolanything` 自動生成
- 不替不存在的 transport、source 類型或 host 行為補文件
- 不假設 GitHub Wiki 已經啟用；目前請先把 `wiki/` 視為待同步到 `ToolAnything.wiki.git` 的來源
