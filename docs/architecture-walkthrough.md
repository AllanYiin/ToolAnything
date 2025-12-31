# Architecture Walkthrough

> 這份文件說明 ToolAnything 的設計動機、協議邊界與擴充方式。每一節都會指向**實際檔案位置**與**最小範例**，方便你直接對照程式碼。

## A. Repo 的定位與三類使用者

**設計動機**
- ToolAnything 要解決「一份工具程式碼，多協議可用」與「工具搜尋/編排更有效率」的需求。
- 因此 repo 同時提供：協議轉換（OpenAI/MCP）、工具註冊、工具搜尋策略、以及最小 MCP Server。

**實際檔案位置（重要符號）**
- `src/toolanything/decorators/tool.py`：`tool()` decorator，註冊工具入口。
- `src/toolanything/core/registry.py`：`ToolRegistry`，統一工具與 pipeline 的註冊中心。
- `src/toolanything/core/tool_search.py`：`ToolSearchTool`，工具搜尋入口。
- `src/toolanything/core/selection_strategies.py`：`RuleBasedStrategy`、`HybridStrategy`，策略層。

**三類使用者定位**
1. **初學者**：只想把 Python 函數變成可呼叫的工具。
2. **已懂 MCP/JSON-RPC 的開發者**：想要明確知道協議邊界、避免 server/transport 汙染協議層。
3. **進階使用者**：想要做更有效率的工具搜尋/策略化選擇（Phase 4 的成果）。

**最小範例：註冊工具（初學者視角）**
```python
from toolanything.decorators import tool

@tool(name="calculator.add", description="加總兩個整數")
def add(a: int, b: int) -> int:
    return a + b
```

---

## B. 為什麼 protocol 要獨立（protocol core 的責任邊界）

**設計動機**
- MCP JSON-RPC 的 method routing、錯誤格式與 response 結構應該被「協議核心」集中管理。
- 任何 server/transport 都只需要把請求丟給 protocol core，不應再重複實作 MCP method。這讓協議升級與測試都更可控。

**實際檔案位置（重要符號）**
- `src/toolanything/protocol/mcp_jsonrpc.py`：
  - `MCPJSONRPCProtocolCore.handle()`：method routing 的單一入口。
  - `MCPProtocolCoreImpl`：預設 protocol core 的別名。
  - `MCPRequestContext`：由 server/transport 注入的上下文。

**最小範例：Protocol Core 處理入口**
```python
from toolanything.protocol.mcp_jsonrpc import MCPProtocolCoreImpl, MCPRequestContext

protocol = MCPProtocolCoreImpl()
response = protocol.handle(
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    context=MCPRequestContext(user_id="demo", transport="stdio"),
    deps=deps,
)
```
> `deps` 是由 server/transport 注入的 capability/tools/invoker 集合（見 `src/toolanything/server/*`）。

---

## C. 為什麼 server 不能知道 MCP method（如何避免污染）

**設計動機**
- server/transport 只負責 I/O（HTTP/stdio）與組裝 dependencies，不應直接處理 MCP method。
- 這樣任何 transport（HTTP/SSE/stdio/自訂）都能共享同一份 protocol core。

**實際檔案位置（重要符號）**
- `src/toolanything/server/mcp_tool_server.py`：`_build_handler()` 內建立 `_ProtocolDependencies`，透過 `protocol_core.handle(...)` 路由。
- `src/toolanything/server/mcp_stdio_server.py`：`MCPStdioServer.run()` 只負責讀寫 stdin/stdout，並呼叫 `MCPProtocolCoreImpl.handle()`。

**最小範例：server 只做 I/O 與注入依賴**
```python
# 摘自 mcp_stdio_server.py 的概念
context = MCPRequestContext(user_id="default", transport="stdio")
response = self._protocol_core.handle(request, context=context, deps=self._deps)
```

---

## D. 怎麼新增一個 transport（新增 SSE/stdio/其他）

**設計動機**
- 只要新 transport 能把「JSON-RPC request」交給 protocol core，就能與 MCP 行為完全一致。
- 因此擴充 transport 的重點是：I/O + 依賴注入 + context。

**實際檔案位置（重要符號）**
- `src/toolanything/server/mcp_tool_server.py`：HTTP/SSE 版本參考。
- `src/toolanything/server/mcp_stdio_server.py`：stdio 版本參考。
- `src/toolanything/protocol/mcp_jsonrpc.py`：`MCPProtocolCoreImpl` 與 `MCPRequestContext`。

**新增檔案路徑建議**
- 建議新增在：`src/toolanything/server/mcp_<transport>_server.py`

**必實作介面/函式**
- 建立 `_ProtocolDependencies`（capabilities/tools/invoker）。
- 準備 `MCPRequestContext`。
- 呼叫 `MCPProtocolCoreImpl.handle(request, context=..., deps=...)`。

**最小可跑示例（Pseudo-code）**
```python
# src/toolanything/server/mcp_websocket_server.py
from toolanything.protocol.mcp_jsonrpc import MCPProtocolCoreImpl, MCPRequestContext

class MCPWebSocketServer:
    def __init__(self, registry):
        self.protocol = MCPProtocolCoreImpl()
        self.deps = _ProtocolDependencies(...)

    async def on_message(self, payload: dict) -> None:
        context = MCPRequestContext(user_id="default", transport="websocket")
        response = self.protocol.handle(payload, context=context, deps=self.deps)
        if response is not None:
            await self.send_json(response)
```

---

## E. 怎麼新增一個 tool strategy（Phase 4 的策略層）

**設計動機**
- 工具搜尋與排序不只要看相似度，還要考慮 failure_score、metadata 等因素。
- 策略層讓你可以替換排序規則，甚至導入 embedding-based 的搜尋。

**實際檔案位置（重要符號）**
- `src/toolanything/core/selection_strategies.py`：
  - `BaseToolSelectionStrategy`
  - `RuleBasedStrategy`
  - `HybridStrategy`
- `src/toolanything/core/tool_search.py`：`ToolSearchTool` + `build_search_tool()`
- `src/toolanything/cli.py`：`search` CLI 使用 `ToolSearchTool`。

**最小範例：自訂策略並掛上 ToolSearchTool**
```python
from toolanything.core.selection_strategies import BaseToolSelectionStrategy, SelectionOptions
from toolanything.core.tool_search import ToolSearchTool

class AlwaysFirstStrategy(BaseToolSelectionStrategy):
    def select(self, tools, *, options: SelectionOptions, failure_score, now=None):
        return list(tools)[: options.top_k]

searcher = ToolSearchTool(registry, failure_log, strategy=AlwaysFirstStrategy())
results = searcher.search(query="weather")
```

**如何接到 ToolSearchTool 或 CLI**
- ToolSearchTool：直接在初始化時注入 `strategy=...`。
- CLI：可以在 CLI 的 `search` 流程中替換 `ToolSearchTool` 初始化（檔案：`src/toolanything/cli.py`）。

---

## F. Tool metadata 的設計（Phase 4 的 metadata schema）

**設計動機**
- metadata 讓工具搜尋與排序可以考慮成本、延遲與副作用，而不是只看文字相似度。
- 同時保留向下相容：舊工具不填 metadata 仍可用。

**實際檔案位置（重要符號）**
- `src/toolanything/core/metadata.py`：`ToolMetadata`、`normalize_metadata()`
- `src/toolanything/core/models.py`：`ToolSpec.metadata`、`ToolSpec.normalized_metadata()`
- `src/toolanything/core/selection_strategies.py`：`RuleBasedStrategy._filter_by_metadata()`

**最小範例：註冊 metadata 並讀取**
```python
from toolanything.decorators import tool

@tool(
    name="flight.search",
    description="搜尋航班",
    metadata={
        "cost": 0.02,
        "latency_hint_ms": 1200,
        "side_effect": False,
        "category": "travel",
        "tags": ["flight", "search"],
        "extra": {"provider": "demo"},
    },
)
def search_flight(origin: str, dest: str):
    return {"origin": origin, "dest": dest}
```
> `normalize_metadata()` 會把未知欄位保留在 `extra`，不影響舊工具。

---

## G. End-to-end 流程（從啟動到工具呼叫）

**設計動機**
- MCP flow 必須涵蓋初始化、列出工具、搜尋工具、與工具呼叫。
- ToolAnything 也把 failure_score 納入搜尋排序，避免近期失敗頻繁的工具搶到前面順位。

**實際檔案位置（重要符號）**
- 初始化/列表/呼叫：`src/toolanything/protocol/mcp_jsonrpc.py`（`MCPJSONRPCProtocolCore.handle`）
- server 啟動：`src/toolanything/server/mcp_tool_server.py`（`run_server`）
- stdio 啟動：`src/toolanything/server/mcp_stdio_server.py`（`run_stdio_server`）
- 失敗排序：`src/toolanything/core/failure_log.py`（`FailureLogManager.failure_score`）
- 搜尋入口：`src/toolanything/core/tool_search.py`（`ToolSearchTool.search`）

**最小範例：stdio 方式完成 initialize → tools/list → tools/call**
```python
import json
import subprocess
import sys
from pathlib import Path

from toolanything.protocol.mcp_jsonrpc import (
    MCP_METHOD_INITIALIZE,
    MCP_METHOD_NOTIFICATIONS_INITIALIZED,
    MCP_METHOD_TOOLS_LIST,
    MCP_METHOD_TOOLS_CALL,
    build_notification,
    build_request,
)

module_path = Path("examples/quickstart/tools.py")
cmd = [sys.executable, "-m", "toolanything.cli", "serve", str(module_path), "--stdio"]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

proc.stdin.write(json.dumps(build_request(MCP_METHOD_INITIALIZE, 1)) + "\n")
proc.stdin.flush()
print(proc.stdout.readline())  # initialize response

proc.stdin.write(json.dumps(build_notification(MCP_METHOD_NOTIFICATIONS_INITIALIZED, {})) + "\n")
proc.stdin.flush()

proc.stdin.write(json.dumps(build_request(MCP_METHOD_TOOLS_LIST, 2)) + "\n")
proc.stdin.flush()
print(proc.stdout.readline())  # tools/list response

proc.stdin.write(
    json.dumps(
        build_request(
            MCP_METHOD_TOOLS_CALL,
            3,
            params={"name": "calculator.add", "arguments": {"a": 1, "b": 2}},
        )
    )
    + "\n"
)
proc.stdin.flush()
print(proc.stdout.readline())  # tools/call response

proc.stdin.close()
proc.wait()
```

**failure_score 如何影響排序**
- `FailureLogManager.failure_score()` 在 `RuleBasedStrategy.select()` 中被使用（`src/toolanything/core/selection_strategies.py`），
  近期失敗多的工具會被排序到較後面，避免被優先選中。

---

## 延伸閱讀

- `docs/README.md`：文件索引
- `examples/quickstart/README.md`：最小可跑範例
