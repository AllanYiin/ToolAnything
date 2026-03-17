# CLI Reference

這一頁是查詢型參考文件，整理 ToolAnything CLI 的主要子命令、用途與常見用法。

## Overview

目前 CLI 聚焦在五件事：啟動 server、診斷 transport、搜尋工具、啟動 inspector，以及產生 Claude Desktop 設定。

Version scope：這份參考頁以 `0.1.0` 版 CLI 為準。

## 命令總覽

| 命令 | 用途 |
| --- | --- |
| `run-mcp` | 啟動內建 MCP Tool Server |
| `run-streamable-http` | 啟動內建 Streamable HTTP transport |
| `run-stdio` | 啟動內建 stdio server |
| `serve` | 載入使用者工具模組並啟動 server |
| `init-claude` | 產生 Claude Desktop MCP 設定片段 |
| `install-claude` | 直接寫入 Claude Desktop 設定檔 |
| `search` | 搜尋已註冊工具，支援 metadata / constraints |
| `examples` | 列出範例入口 |
| `doctor` | 檢查 transport、initialize、`tools/list`、`tools/call` |
| `inspect` | 啟動 Web 版 MCP Test Client |

## `serve`

```bash
toolanything serve <module-or-path> [--host 127.0.0.1] [--port 9090] [--stdio|--streamable-http|--legacy-http]
```

重點：

- `module` 同時支援 Python 模組路徑與 `.py` 檔案路徑
- `--stdio` 用於 Desktop host
- `--streamable-http` 用於新版 `/mcp`
- `--legacy-http` 用於舊 client 相容
- 不帶 transport flag 時，會啟動 Streamable HTTP

範例：

```bash
toolanything serve examples/quickstart/tools.py
toolanything serve examples/quickstart/tools.py --stdio
toolanything serve examples/quickstart/tools.py --legacy-http --port 9090
```

### Parameters pattern

`serve` 類命令多半都會共用這些參數型態：

- 模組路徑或檔案路徑
- `--host`
- `--port`
- transport flag

## `doctor`

```bash
toolanything doctor --mode {stdio,http} [--cmd CMD] [--tools TOOLS] [--url URL] [--timeout 8.0] [--json]
```

常見用法：

```bash
toolanything doctor --mode stdio --tools examples.quickstart.tools
toolanything doctor --mode http --url http://127.0.0.1:9092
toolanything doctor --mode stdio --cmd "python -m toolanything.cli serve my_tools.py --stdio"
```

規則：

- `--cmd` 與 `--tools` 不能同時用
- HTTP 模式中，`--url` 不能與 `--cmd` 或 `--tools` 同時用
- `--json` 適合接 CI 或其他自動化

## Responses and outputs

CLI 的常見回應型態有三種：

- 一般 help text
- `doctor --json` 這類結構化輸出
- `search` 回傳的 JSON lines

## `search`

```bash
toolanything search [--query QUERY] [--tags ...] [--prefix PREFIX] [--top-k 10]
                    [--disable-failure-sort] [--max-cost COST]
                    [--latency-budget-ms MS] [--allow-side-effects]
                    [--category CATEGORY]
```

它會依照註冊工具的名稱、描述、tags、metadata 與 failure score 做篩選與排序。

範例：

```bash
toolanything search --query weather --max-cost 0.1 --latency-budget-ms 200
toolanything search --tags finance realtime --allow-side-effects
toolanything search --category routing --category search
```

## `inspect`

```bash
toolanything inspect [--host 127.0.0.1] [--port 9060] [--timeout 8.0] [--no-open]
```

用途：

- 互動式看 schema
- 手動打 `tools/call`
- 檢查 MCP transcript
- 做 OpenAI tool-calling smoke test

## `init-claude` / `install-claude`

```bash
toolanything init-claude --module examples/opencv_mcp_web/server.py --port 9090
toolanything install-claude --module examples/opencv_mcp_web/server.py --port 9090
```

差異：

- `init-claude` 只輸出設定片段
- `install-claude` 會直接更新 Claude Desktop 的 config

## `examples`

```bash
toolanything examples
```

會列出幾個推薦入口，例如 Quickstart、Tool Selection 與 Protocol Boundary。

## Errors and failure modes

常見錯誤包括：

- 模組路徑找不到
- transport 參數互斥衝突
- server 尚未就緒
- 相關 tool 或 API key 缺失

## 相關文件

- [Getting Started](Getting-Started)
- [MCP Serving and Transports](MCP-Serving-and-Transports)
- [Diagnostics and Troubleshooting](Diagnostics-and-Troubleshooting)
