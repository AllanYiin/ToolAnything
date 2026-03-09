# Callable-First 耦合盤點

本文件是 invoker-first 重構前的 Phase 0 基線盤點，只描述現況，不變更設計。

## 目標

- 列出目前 public API 與內部執行流程中，哪些位置仍以 Python callable 為中心。
- 標記後續 Phase 1 / Phase 2 需要拆解的斷點與風險。
- 明確區分「必須維持相容」與「可以重構內核」的部分。

## 現況主線

目前工具執行主線如下：

1. `@tool` decorator 呼叫 `ToolSpec.from_function(...)`。
2. `ToolSpec` 直接持有 `func`。
3. `ToolRegistry.register()` 將 `ToolSpec` 放進 `_tools`。
4. `ToolRegistry.get()` 直接回傳 callable。
5. `ToolRegistry.execute_tool_async()` 取 callable，檢查 context 參數後執行。
6. `ToolManager.invoke()` 與 adapter 層都依賴 `registry.execute_tool_async(...)`。
7. Schema 匯出仍由 `ToolSpec.to_openai()` / `ToolSpec.to_mcp()` 驅動。

## 耦合點盤點

### `src/toolanything/decorators/tool.py`

- `tool()` 在 decorator 入口直接建立 `ToolSpec.from_function(...)`。
- `wrapper.tool_spec = spec` 讓外部可以拿到 function-centric `ToolSpec`。
- 風險：
  - 任何 `ToolSpec` 欄位重構都會直接影響 decorator 行為。
  - 若 `ToolSpec` 不再直接暴露 `func`，既有 `echo.tool_spec.func` 類型使用方式需要 compatibility layer。

### `src/toolanything/core/models.py`

- `ToolSpec` 是 frozen dataclass，核心欄位含 `func: Callable[..., Any]`。
- `ToolSpec.from_function()` 內含 docstring 解析、schema 生成、名稱推導與 callable 綁定。
- `PipelineDefinition` 同樣直接持有 `func`。
- 風險：
  - schema contract、source 設定與 execution body 尚未分層。
  - 任何非 callable source 都會被迫偽裝成函數，導致例外與設定責任混雜。

### `src/toolanything/core/registry.py`

- `_lookup_cache` 型別是 `Dict[Tuple[str | None, str], Callable[..., Any]]`。
- `get()` 快取並回傳 callable，而不是 tool contract / runtime handle。
- `execute_tool_async()` 內建 callable 執行策略：
  - sync function 轉 thread
  - async function 直接 await
  - 自動偵測 `PipelineContext` 參數後注入
- pipeline 與 tool 共用 lookup 路徑，但兩者都依賴 `.func`。
- 風險：
  - registry 同時負責 lookup、runtime policy、context 注入，責任太重。
  - invoker-first 重構若只改表面型別、不拆這條執行路徑，HTTP / SQL / model source 仍會被 callable 假象綁住。

### `src/toolanything/core/tool_manager.py`

- `register()` 以 function 為中心建立 `ToolSpec`。
- `invoke()` 直接把 name/args 丟給 `registry.execute_tool_async()`。
- 風險：
  - manager 缺少 tool contract 與 runtime 邊界；若 registry 改成 invoker-first，manager 需要同步切換到新的 invocation API。

### `src/toolanything/adapters/mcp_adapter.py`

- `to_invocation()` 直接走 `registry.execute_tool_async(...)`。
- schema 匯出依賴 `registry.to_mcp_tools()`，而其底層又依賴 `ToolSpec.to_mcp()`。
- 風險：
  - adapter 目前對 runtime path 的假設是「registry 會自己找到 callable 並執行」。
  - 後續 transport / protocol core 若要支援串流、遠端 source 或其他 execution backend，這個假設必須先拆掉。

### 其他兼容依賴

- `src/toolanything/adapters/openai_adapter.py` 同樣直接呼叫 `registry.execute_tool_async(...)`。
- 多個測試直接斷言 `spec.func(...)` 或 `registry.get(...) is callable`，例如：
  - `tests/test_decorator.py`
  - `tests/test_tool_manager.py`
  - `tests/test_registry_cache.py`
  - `tests/test_registry_namespacing.py`

## 風險分級

### 高風險

- `ToolSpec.func`
- `ToolRegistry.get() -> callable`
- `ToolRegistry._lookup_cache` 快取 callable
- `ToolRegistry.execute_tool_async()` 直接執行 function

這些是 invoker-first 重構的主斷點，不拆就無法乾淨支援非 callable source。

### 中風險

- `ToolManager.register()` 的 function-first 註冊入口
- `MCPAdapter` / `OpenAIAdapter` 對 registry runtime path 的假設

這些可以保留 public API，但內部必須改走新的 invoker path。

### 低風險

- `to_openai_tools()` / `to_mcp_tools()` 的 schema 外觀
- `@tool` decorator 的使用體驗

這些屬於 Phase 0 明確要求維持不變的 outward behavior。

## 向前相容邊界

本輪重構至少保證以下項目在一個版本週期內持續可用：

- `@tool` decorator 的基本用法不變。
- `ToolSpec.from_function()` 仍可從 Python function 建立工具。
- 現有 function tool 的 OpenAI / MCP schema 外觀保持相容。
- `ToolManager.invoke()`、`ToolRegistry.execute_tool_async()` 對既有 function tool 的行為保持相容。

## Phase 1 / Phase 2 重構重點

- Phase 1：把 `ToolSpec` 從直接持有 callable 改為持有 contract + invoker 關聯資訊。
- Phase 1：新增 `CallableInvoker` 吸收 sync/async/context 注入邏輯。
- Phase 2：把 registry / manager / adapter 的 runtime path 改成「查 tool contract -> 取 invoker -> invoke」。
- Phase 2：保留 callable API 作為 compatibility layer，而不是核心抽象。
