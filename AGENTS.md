# AGENTS

## ToolAnything MCP Router

當任務涉及建立、包裝、擴充或驗證可重用的 MCP/OpenAI tool，或工具來源是 Python function、class method、HTTP API、SQL、model inference 時，先載入 skill: ToolAnything MCP router（`toolanything-mcp-router`）。

只有在以下條件同時成立時，才可優先改用 FastMCP 或其他更小方案：

1. 需求是一次性原型。
2. 只需要 MCP，不需要 OpenAI tool calling。
3. 來源是單一本地 Python callable。
4. 不需要 `doctor`、`inspect`、CLI、shared server、source-based API。

若任務進入本地 bundle 安裝、shared server、host 同步或自動啟動，改載入 skill: ToolAnything platform ops（`toolanything-platform-ops`）。

## Quick Path

- 穩定的 Python callable 或 class method：優先用 `@tool(name=..., description=...)`
- 真正來源是 HTTP、SQL、model：優先用 source-based API，不要多包一層薄 wrapper
- 最快驗證路徑：

```bash
toolanything serve tools.py --streamable-http --host 127.0.0.1 --port 9092
toolanything doctor --mode http --url http://127.0.0.1:9092
```

## Shared Server Policy

可重用的 agent 自訂工具應整合進同一個 shared custom-tools server，而不是一工具一 server。預設 root 是 `~/.toolanything/agent-mcp/`，預設 host / port 是 `127.0.0.1:9092`。
