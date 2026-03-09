# Invoker-First Migration Baseline

本文件是 Phase 0 的 migration baseline，用來鎖定重構前的對外承諾與相容邊界。

## 這輪重構要解決的問題

目前 ToolAnything 的核心假設是「工具等於 Python function」。這個假設在只支援 `@tool` function 時很直接，但當來源擴展到 HTTP API、SQL query、PyTorch / ONNX model、remote MCP proxy 時，會帶來三個結構性問題：

1. tool contract、來源設定與執行策略混在同一個 `ToolSpec`。
2. registry 直接回傳 callable，讓 runtime 無法獨立演化。
3. transport / adapter 被迫依賴 function-centric 的執行路徑。

本輪重構的方向是把核心改為 invoker-first：工具不一定要綁 Python callable，只要能被統一 `invoke(...)` 即可。

## Phase 0 明確承諾

在完成 Phase 0 後，以下行為被視為 compatibility baseline，後續 Phase 1 / Phase 2 不得無意破壞：

- `@tool` decorator 仍可註冊既有 function tools。
- `ToolManager.invoke()` 仍可執行 sync / async function tools。
- `ToolRegistry.execute_tool_async()` 仍支援 context 自動注入。
- `to_openai_tools()` 與 `to_mcp_tools()` 的 schema 外觀維持不變。
- `MCPAdapter.to_invocation()` 對成功與錯誤情境的輸出維持相容。

這些承諾由 `tests/test_refactor_phase0_baseline.py` 與 `tests/golden/` 下的 snapshot 檔案鎖定。

## 新舊核心定位

### 舊核心

- 中心抽象：callable
- 註冊入口：`ToolSpec.from_function(...)`
- runtime：`ToolRegistry.execute_tool_async(...)`
- adapter 假設：registry 會直接找到 callable 並執行

### 新核心

- 中心抽象：invoker
- contract：工具名稱、描述、input schema、metadata
- source：function / HTTP / SQL / model 等來源設定
- runtime：建立 execution context 後交給 invoker 執行
- transport：只負責 request/response 與 streaming，不直接耦合工具實作

## Compatibility Layer 策略

舊 API 不會在這輪立即刪除，而是先降級為 compatibility layer：

- `@tool`
- `ToolSpec.from_function()`
- function-based `ToolManager.register(...)`
- function tool 的既有 schema 匯出與 invocation 行為

新的核心抽象會優先支援 invoker/source-based 設計；callable 只是其中一種 source，而不再是整個系統的預設世界觀。

## 不在本輪 scope 的項目

以下項目不在這一輪 migration baseline 的執行範圍內：

- skill as tool
- 完整 OpenAPI importer
- OAuth 完整流程
- model training / distributed orchestration
- resources / prompts 全面擴充

## Phase 對應

- Phase 0：鎖定現況與建立 regression safety net
- Phase 1：引入 invoker-first 核心抽象，但保留 callable compatibility
- Phase 2：registry / manager / adapter 切到 invoker runtime path
- Phase 3 之後：逐步加入 HTTP / SQL / model source 與新的 transport

## 驗收標準

後續每個 phase 至少要同時滿足兩件事：

1. Phase 0 baseline 測試持續通過。
2. 新抽象不再把 Python callable 當成唯一合法來源。
