---
name: toolanything-tool-wrapper
description: 當使用者要用 ToolAnything 把 Python function、class method 或既有程式入口包裝成可供 agent、MCP 或 OpenAI tool calling 使用的工具時使用。適用於新增 @tool、調整 ToolRegistry 註冊、把既有函數暴露成 tools、驗證 tools/list 與 tools/call，或判斷何時該改用 register_http_tool、register_sql_tool、register_model_tool 而不是硬寫 wrapper。
version: 2026.3.16
license: MIT
metadata:
  author: OpenAI Codex
  repo: ToolAnything
---

# ToolAnything Tool Wrapper

這個 skill 的目標是讓 agent 用 ToolAnything 的原生 API，把可呼叫能力正確暴露成工具，而不是額外堆一層脆弱 glue code。

## 先做什麼

先讀最小必要上下文，不要一開始就把整個 repo 掃過一遍：

1. `README.md`
2. `examples/quickstart/README.md`
3. `examples/quickstart/01_define_tools.py`
4. `src/toolanything/decorators/tool.py`
5. `src/toolanything/core/models.py`

只有在需求真的涉及 class method、source-based tool 或 transport 驗證時，再往下讀：

- class method：`examples/class_method_tools/README.md`
- source-based tool：`examples/non_function_tools/README.md` 與對應範例
- CLI / 驗證：`src/toolanything/cli.py`

## 核心 use cases

### 1. 把 Python function 包成可調用 tool

常見 trigger：

- 「用 ToolAnything 把這個函數包成 tool」
- 「讓 agent 可以呼叫這個 Python function」
- 「把這個 function 暴露成 MCP / OpenAI tools」

Done looks like：

- 使用 `@tool(...)` 或等價 registry 流程完成註冊
- 工具名稱、description、參數 schema 都合理
- 至少做一次本地註冊或呼叫驗證

### 2. 把 class method 包成 tool

常見 trigger：

- 「把這個 class method 變成 tool」
- 「ToolAnything 能不能包 classmethod」

Done looks like：

- 使用 repo 已支援的 decorator 疊法
- 不需要手動傳 `cls`
- 能透過 registry 或 CLI 驗證 callable 正常

### 3. 判斷不該硬寫 wrapper 的情況

常見 trigger：

- 「把 HTTP API / SQL / model 接成 tool」
- 「我不想再多寫一層 Python wrapper」

Done looks like：

- 明確指出應改走 `register_http_tool`、`register_sql_tool` 或 `register_model_tool`
- 使用對應 `SourceSpec`
- 沒有額外發明低價值 wrapper

## 執行流程

### Phase 1. 先判斷是哪一種工具來源

1. 如果來源本來就是穩定的 Python callable，優先用 `@tool`。
2. 如果來源其實是 HTTP endpoint、SQL query 或 model artifact，優先用 source-based API，不要硬包成薄 wrapper。
3. 如果使用者把 ToolAnything 當成全能 agent framework，直接糾正：這個 repo 主要處理 tool definition、schema、runtime 與 transport，不負責替你設計完整 orchestration。

### Phase 2. 實作 callable-backed tool

1. 保持函數簽名清楚，參數型別要能穩定轉成 schema。
2. 預設顯式寫 `@tool(name=..., description=...)`，不要把穩定契約賭在自動推導名稱。
3. 若要讓工具搜尋、成本或副作用可控，再補 `tags` 與 `metadata`；不要無意義塞滿欄位。
4. 工具名稱優先用穩定的領域名稱，例如 `weather.query`、`calculator.add`，不要用臨時命名。
5. 若需要隔離測試或避免污染全域 registry，再傳入顯式 `registry=`；否則可接受全域 registry。

### Phase 3. 實作 class method tool

1. ToolAnything 已支援 `@tool` 與 `@classmethod` 兩種順序。
2. 若專案附近已有慣例，跟隨現有風格。
3. 若沒有既有慣例，優先讓 `@tool(...)` 放外層，因為 metadata 較容易掃讀。
4. 不要自己手寫 descriptor workaround；repo 內建註冊流程已處理這件事。

### Phase 4. 驗證

至少做一層驗證，能做兩層更好：

1. 模組層：匯入模組或執行腳本，確認工具確實註冊。
2. Registry 層：列出工具、直接呼叫 `execute_tool`，或跑對應範例。
3. CLI 層：用 `toolanything doctor` 驗證 `tools/list` / `tools/call`。
4. Transport 層：若需求包含網路連線，再用 `serve` 啟動 `stdio` 或 `streamable-http`。
5. 偵錯層：需要看 transcript 或手動 call 時再開 `toolanything inspect`。

如果不確定 `toolanything` 命令是否已安裝在 PATH，優先用 `python -m toolanything.cli ...`。

## 必守邊界

1. 不要為了「看起來像工具」去改動 runtime、transport 或 adapter 的核心行為，除非需求真的在那裡。
2. 不要為了單一任務隨意更名既有工具；工具名稱通常就是契約。
3. 不要重造第二套 schema 或 name mapping，ToolAnything 已處理 MCP 與 OpenAI schema。
4. 不要把 source-based tool 偽裝成 function-only 問題，這會讓解法退化。
5. 若使用者的想法不對，直接指出錯誤並說明為什麼，例如「這個需求其實不是再包 function，而是應該直接註冊 HTTP source」。

## 交付時要回報什麼

至少交代三件事：

1. 你選了 `@tool` 還是 source-based API，理由是什麼。
2. 改了哪些檔案，工具名稱與契約如何定義。
3. 跑了哪些驗證；若沒跑，阻塞點是什麼。

需要具體範例、判斷矩陣與命令清單時，讀：

- `references/workflow.md`
- `references/verification.md`
