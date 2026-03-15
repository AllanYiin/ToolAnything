# Architecture Walkthrough

> 這份文件是「設計敘事 + 擴充指南」，不是 API 文件。每一章都對應至少一個**真實檔案路徑**與**真實符號**，方便你直接對照程式碼。

## Repo 定位與三類使用者

ToolAnything 的定位是「跨協議 AI 工具中介層」：一份工具定義可以輸出到 MCP 與 OpenAI Tool Calling。現在核心已從 callable-first 重構為 invoker-first，一份工具不一定要綁定 Python function；`@tool` 也可直接處理 class method，另外工具也可以來自 HTTP、SQL 或 model inference source。對應三類使用者：

1. **初學者**：只需要把 Python 函式或 class method 變成可呼叫的工具。
2. **已有 MCP 概念者**：關注協議邊界、transport 與 protocol core 的責任切割。
3. **進階使用者**：需要搜尋、排序與策略化選擇工具。

**對照位置與符號**
- `src/toolanything/decorators/tool.py`：`tool()` decorator 是工具註冊入口。
- `src/toolanything/core/models.py`：`ToolContract` / `ToolSpec` 是工具契約與相容層入口。
- `src/toolanything/core/invokers/`：`CallableInvoker`、`HttpInvoker`、`SqlInvoker`、`ModelInvoker`。

## Invoker-First 分層

核心分成五層：

1. `SourceSpec`：來源設定，例如 HTTP/SQL/model。
2. `ToolContract`：name / description / input schema / metadata。
3. `Invoker`：實際執行邏輯。
4. `Runtime`：建立 `ExecutionContext`、查 invoker、維持 compatibility API。
5. `Transport`：stdio / Streamable HTTP / legacy SSE，只做 I/O。

**對照位置與符號**
- `src/toolanything/core/source_specs.py`
- `src/toolanything/core/models.py`
- `src/toolanything/core/runtime_types.py`
- `src/toolanything/core/registry.py`
- `src/toolanything/server/mcp_streamable_http.py`

```mermaid
flowchart LR
    A["SourceSpec"] --> B["ToolContract"]
    A --> C["Invoker"]
    B --> D["ToolRegistry Runtime"]
    C --> D
    D --> E["Adapters"]
    D --> F["Transports"]
```

**最小概念示例**
```python
from toolanything.decorators import tool


@tool(name="quickstart.greet", description="打招呼")
def greet(name: str) -> str:
    return f"Hello {name}"
```

若你要的是 class method 版本，另可參考 `examples/class_method_tools/README.md`。

## 為什麼 protocol 要獨立（指出 protocol core 的入口與責任）

協議核心負責 JSON-RPC method routing、錯誤格式與回應包裝，避免每個 server/transport 重新實作 MCP method。

**對照位置與符號**
- `src/toolanything/protocol/mcp_jsonrpc.py`：`MCPJSONRPCProtocolCore.handle()` 是 method routing 的唯一入口。
- `src/toolanything/protocol/mcp_jsonrpc.py`：`MCPProtocolCoreImpl` 指向預設實作。

**責任重點**
- protocol core 處理 `initialize` / `tools/list` / `tools/call`。
- transport/server 只注入 capability、tool schema、tool invoker 與 context。

## 為什麼 server/transport 不知道 MCP method（指出 server 僅 I/O，method routing 在哪）

server/transport 只處理 I/O 與依賴注入，method routing 由 protocol core 統一處理。

**對照位置與符號**
- `src/toolanything/server/mcp_streamable_http.py`：`MCPStreamableHTTPHandler.do_POST()` 將 request 轉交給 `protocol_core.handle(...)`。
- `src/toolanything/server/mcp_tool_server.py`：legacy SSE compatibility handler。
- `src/toolanything/protocol/mcp_jsonrpc.py`：`MCPJSONRPCProtocolCore.handle()` 實際做 method routing。

**設計結果**
- 任何 transport（HTTP/SSE/stdio）都可共用同一份 MCP method 行為。
- server 只需關心如何讀/寫與 session context。

## 怎麼新增一個 transport（以現有 SSE/STDIO 對照，給出最小新增步驟）

新增 transport 的重點是：**I/O + 依賴注入 + MCPRequestContext**。

**對照位置與符號**
- `src/toolanything/server/mcp_streamable_http.py`：`_build_handler()` 展示 Streamable HTTP 的 session/auth/header 邊界。
- `src/toolanything/server/mcp_tool_server.py`：legacy SSE transport。
- `src/toolanything/server/mcp_stdio_server.py`：`MCPStdioServer.run()` 展示 stdio 讀寫。
- `src/toolanything/server/mcp_runtime.py`：共享 protocol dependency wiring。
- `src/toolanything/protocol/mcp_jsonrpc.py`：`MCPRequestContext`。

**最小新增步驟**
1. 建立新的 transport server（例如 `src/toolanything/server/mcp_websocket_server.py`）。
2. 透過 `build_protocol_dependencies(...)` 建立 capabilities/tools/invoker。
3. 將收到的 JSON-RPC request 交給 `MCPProtocolCoreImpl.handle(...)`。
4. 將 response（若非 `None`）回寫到 transport 的輸出通道。

## 怎麼新增一種 source（HTTP / SQL / model）

新增 source 的重點是：**SourceSpec + schema compiler + Invoker + register API**。

**對照位置與符號**
- `src/toolanything/core/http_tools.py`
- `src/toolanything/core/sql_tools.py`
- `src/toolanything/core/model_tools.py`
- `src/toolanything/core/tool_manager.py`：`register_http_tool()` / `register_sql_tool()` / `register_model_tool()`

**最小做法**
1. 定義 `SourceSpec`。
2. 讓 schema compiler 從來源設定產生 input schema。
3. 實作對應 `Invoker`。
4. 透過 `ToolSpec(..., invoker=...)` 編譯成正式工具。

## 怎麼新增一個 tool strategy（指出策略介面與預設策略，如何接到 ToolSearchTool/CLI）

搜尋策略負責「篩選 + 排序」，預設以 `RuleBasedStrategy` 執行（文字相似度 + metadata 條件）。

**對照位置與符號**
- `src/toolanything/core/selection_strategies.py`：`BaseToolSelectionStrategy`、`RuleBasedStrategy`。
- `src/toolanything/core/tool_search.py`：`ToolSearchTool` 注入策略。
- `src/toolanything/core/semantic_search.py`：`SemanticToolIndex`、`SemanticRetrievalStrategy`、`JinaOnnxEmbeddingsV5TextNanoRetrievalProvider`。
- `src/toolanything/cli.py`：`_run_search()` 使用 `ToolSearchTool`。

**最小做法（自訂策略 → 注入 ToolSearchTool）**
```python
from toolanything.core.selection_strategies import BaseToolSelectionStrategy, SelectionOptions
from toolanything.core.tool_search import ToolSearchTool

class AlwaysFirstStrategy(BaseToolSelectionStrategy):
    def select(self, tools, *, options: SelectionOptions, failure_score, now=None):
        return list(tools)[: options.top_k]

searcher = ToolSearchTool(registry, failure_log, strategy=AlwaysFirstStrategy())
results = searcher.search(query="demo")
```

**可選的語意搜尋路線**
- `SemanticToolIndex` 會把 tool 的名稱、描述、metadata、輸入 schema 組成搜尋文件，並快取成可索引文本。
- `SemanticRetrievalStrategy` 保留既有 tags/prefix/metadata 篩選，再改用語意相似度排序。
- `JinaOnnxEmbeddingsV5TextNanoRetrievalProvider` 採 lazy import；只有真的呼叫語意搜尋時才會載入 `onnxruntime`、`transformers`、`huggingface-hub` 與 `numpy`，不會把依賴變成核心安裝門檻。

## Tool metadata 設計（cost/latency_hint_ms/side_effect/category/tags/extra）與向下相容策略

metadata 提供成本、延遲、副作用等訊號，讓搜尋可依條件篩選。未填 metadata 的舊工具仍可用，未知欄位會被保留在 `extra`。

**對照位置與符號**
- `src/toolanything/core/metadata.py`：`ToolMetadata`、`normalize_metadata()`。
- `src/toolanything/core/models.py`：`ToolSpec.normalized_metadata()`。
- `src/toolanything/core/selection_strategies.py`：`RuleBasedStrategy._filter_by_metadata()`。

**向下相容策略**
- 未提供欄位 → 以 `None` 視為「未知」，不會被硬性排除。
- 未知欄位 → `normalize_metadata()` 會留在 `extra`。

## End-to-end 流程（initialize → tools/list → tool search → tools/call）

以下用文字與 Mermaid 表示資料流，協議處理都集中在 `MCPJSONRPCProtocolCore.handle()`。

**對照位置與符號**
- `src/toolanything/protocol/mcp_jsonrpc.py`：`MCPJSONRPCProtocolCore.handle()`。
- `src/toolanything/core/tool_search.py`：`ToolSearchTool.search()`。
- `src/toolanything/core/registry.py`：`ToolRegistry.invoke_tool_async()`。

**文字流程**
1. Client 發出 `initialize`。
2. Protocol core 透過 `MCPCapabilitiesProvider` 回傳能力資訊。
3. Client 呼叫 `tools/list`，protocol core 透過 `MCPToolSchemaProvider.list_tools()` 回傳工具清單。
4. 本地或外部工具搜尋（`ToolSearchTool.search()`）挑選候選工具。
5. Client 發出 `tools/call`，protocol core 透過 `MCPToolInvoker.call_tool()` 執行並回傳結果。

```mermaid
sequenceDiagram
    participant Client
    participant Transport
    participant ProtocolCore
    participant Registry
    participant Search

    Client->>Transport: JSON-RPC initialize
    Transport->>ProtocolCore: handle(request, context, deps)
    ProtocolCore-->>Client: capabilities

    Client->>Transport: JSON-RPC tools/list
    Transport->>ProtocolCore: handle(request, context, deps)
    ProtocolCore-->>Client: tools schema

    Client->>Search: ToolSearchTool.search(query)
    Search->>Registry: registry.list()
    Search-->>Client: ranked tools

    Client->>Transport: JSON-RPC tools/call
    Transport->>ProtocolCore: handle(request, context, deps)
    ProtocolCore->>Registry: ToolRegistry.invoke_tool_async()
    ProtocolCore-->>Client: tool result
```

## 當前 transport 建議

- 首選：`Streamable HTTP`
- 相容：`STDIO`
- legacy compatibility：舊 `SSE / messages/{session_id}`

`skill as tool` 尚未納入這一輪設計；目前文件、source API 與 transport 邊界都以 callable/http/sql/model 為主。

## 延伸閱讀

- `docs/docs-map.md`
- `examples/quickstart/README.md`
