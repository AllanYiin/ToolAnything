# 規格整理 v 1.2.0

```md
[關鍵概念定義]
- MCP Client：負責與 MCP Server 建立 transport、送出 initialize / tools/list / tools/call 的客戶端。
- MCP Inspector：官方提供的互動式測試工具，重點是連線、協議除錯、工具探索與 traffic 檢查。
- LLM 工具調用測試：驗證模型是否會根據提示選擇工具、產生合法參數、並正確消化工具結果。
- 對 ToolAnything 的影響：repo 已有 doctor CLI、dummy client 與特定 Web tester；本功能應整併成正式、通用、可重用的內建測試 client。
```

```md
[競品 / 類似服務比較]
| 對象 | 做法 | 優點 | 缺點 | 可借鏡處 |
|---|---|---|---|---|
| MCP Inspector 官方工具 | GUI + CLI + proxy | 生態標準、能看協議細節 | 引入 Node 工具鏈，超出本 repo 現況 | 連線設定、工具探索、協議回應可視化 |
| ToolAnything doctor | CLI 自動測 initialize/tools/list/tools/call | 適合 CI、自動化 | 缺乏圖形界面與互動式工具測試 | 重用現有測試邏輯與報告格式 |
| ToolAnything OpenCV Web demo | 靜態頁面 + ToolAnything 端點 | 已有 Web UI 雛形 | 綁死特定工具，不是通用 MCP client | 重用 UI 骨架與靜態資產模式 |
| Dummy MCP client 範例 | Python 腳本驗證 health/tools/invoke | 簡單易懂 | 只能做 smoke test，不能互動探索 | 保留為最小 roundtrip 參考 |
```

```md
[GitHub / 開源 repo 比較]
| Repo | 技術路線 | 亮點 | 風險 / 侷限 | 可借鏡處 |
|---|---|---|---|---|
| modelcontextprotocol/inspector | React + Node + SDK | 官方、功能完整 | 對本 repo 來說太重 | 連線配置、tool explorer、JSON-RPC 檢視 |
| 本 repo examples/mcp_server_demo/client.py | Python urllib client | 輕量、適合 smoke test | 不通用、無 GUI | 最小 HTTP roundtrip |
| 本 repo examples/opencv_mcp_web/web | 靜態 HTML/CSS/JS | 無建置工具，易整合 | 只支援特定 OpenCV 工具 | Web-first MVP UI 方案 |
| 本 repo core/connection_tester.py | Python transport tester | 已有 stdio/http 診斷 | 未抽成互動式 client 能力 | 作為 backend 測試核心 |
```

```md
[建議方案與待確認事項]
- 建議方向：做內建 Web 版 MCP Test Client，不做桌面版 v1。
- 為什麼不是桌面先做：桌面版會放大封裝、安裝、更新與跨平台壓力，與當前 repo 技術棧不匹配。
- v1 核心能力：
  1. 設定 transport（MCP HTTP SSE / stdio）
  2. 一鍵測 initialize/tools/list/tools/call
  3. 瀏覽工具清單與手動呼叫工具
  4. 可選填 OpenAI API key + model，驗證 LLM 是否能挑選並調用工具
- 本次直接採單回合模式完成規格並進入實作。
```

## 技術規格文件

### 假設與前提
- 本次只做 Web-first MVP，不提供桌面封裝。
- MCP HTTP 模式以本 repo 現行支援的 `GET /sse` + `POST /messages/{session_id}` 為主。
- LLM 工具調用測試先支援 OpenAI API，並要求使用者自行輸入 API key 與 model。
- 介面預設淺色模式，並採無前端建置工具的靜態資產方案，降低整合成本。

### 背景
ToolAnything 目前有 `doctor` CLI、HTTP/stdio server、dummy client 範例與特定 Web demo，但缺少正式、通用、內建的測試 client。這會讓使用者在驗證「server 是否接通」、「tools/list 是否正常」、「工具能不能手動呼叫」和「LLM 是否會挑對工具」時，必須在 CLI、範例腳本與外部工具之間切換。

這個落差會直接影響除錯效率，也會讓 ToolAnything 對新使用者顯得不完整。既然 repo 本身的核心定位就是跨協議 AI 工具中介層，內建測試 client 屬於自然且高價值的產品補強。

### 目標
- 提供一個內建命令啟動 Web 版 MCP Test Client。
- 讓使用者可設定 transport、URL/command、user_id 並完成 roundtrip 測試。
- 讓使用者可載入工具清單、手動輸入參數、直接呼叫工具。
- 若提供 OpenAI API key 與 model，可驗證 LLM 是否會正確產生工具呼叫並執行。
- 成功標準：
  - 本 repo 測試可覆蓋 stdio 與 HTTP 模式。
  - 不需額外 Node/前端建置工具即可啟動。
  - 全量測試通過。

### 範圍
- 新增 `toolanything inspect` CLI 子命令。
- 新增一個 FastAPI 應用提供靜態 Web UI 與 backend API。
- 新增通用的 stateless MCP session service，支援 stdio 與 HTTP SSE。
- 新增 OpenAI LLM 工具調用測試流程。
- 新增必要文件與測試。

### 不做什麼
- 不做桌面版封裝。
- 不做官方 Inspector 等級的完整 traffic timeline / raw packet replay。
- 不支援非 OpenAI 的 LLM 供應商。
- 不支援 MCP resources/prompts explorer。
- 不做帳號登入、多使用者權限與雲端存檔。

### Persona
| Persona | 角色 | 主要痛點 | 本功能價值 |
|---|---|---|---|
| 套件使用者 | 正在開發 ToolAnything 工具的人 | 不知道 server 到底是 transport 壞掉還是 schema/工具壞掉 | 一個地方完成連線與工具驗證 |
| 整合測試者 | 要把 ToolAnything 接到外部 agent/LLM 的人 | 難以快速驗證工具是否真的可被模型調用 | 直接做 LLM 工具調用 smoke test |
| 維護者 | 維護 repo 與 examples 的人 | 範例分散、測試路徑不一致 | 收斂成正式內建測試入口 |

### 系統說明
系統由三層組成：Web UI、Inspector API、MCP session service。Web UI 負責收集 transport 設定、顯示測試報告、呈現工具表單與 LLM transcript；Inspector API 負責接住表單請求、調用 MCP session service 與 OpenAI API；MCP session service 以短生命週期 session 方式連到目標 MCP server，統一處理 initialize、tools/list、tools/call。

這樣的切分可以避免把協議細節散落在前端，也能讓 CLI、未來 API、自動化測試共用同一套 session 核心。

### 核心流程設計
1. 使用者執行 `toolanything inspect --port 9060`。
2. 瀏覽器打開 Web UI，選擇 transport：
   - `mcp-http-sse`
   - `stdio`
3. 使用者輸入：
   - HTTP：base URL
   - stdio：command
   - 可選 `user_id`
4. 點「檢查連線」：
   - backend 建立暫時 session
   - 執行 initialize / tools/list / tools/call（若有可呼叫工具）
   - 回傳測試報告
5. 點「載入工具」：
   - backend 建立暫時 session
   - initialize + tools/list
   - UI 顯示工具與 schema
6. 使用者選擇工具並填參數後點「執行工具」：
   - backend 建立暫時 session
   - initialize + tools/call
   - UI 顯示 JSON 結果
7. 若使用者填入 OpenAI API key、model 與 prompt：
   - backend 先 tools/list
   - 轉成 OpenAI tools
   - 呼叫 OpenAI Chat Completions
   - 若模型回傳 tool_calls，backend 呼叫 MCP tools/call
   - 需要時再做第二輪 completion
   - UI 顯示 transcript、tool traces、最終回答

### 開發應注意重點以及應避開誤區
- 不要把 Web UI 直接綁死在 ToolAnything 的 `/invoke` 專屬端點，主路徑應該走 MCP initialize/tools/list/tools/call。
- 不要一開始就做持久連線管理與多分頁 session，同一個 API request 內建短生命週期 session 即可。
- 不要讓前端直接碰 OpenAI API key；必須由 backend 代打，避免瀏覽器暴露密鑰。
- 不要要求前端建置工具；本 repo 現況更適合靜態 HTML/CSS/JS。
- LLM 測試不應與基本連線測試耦合成單一流程，避免定位問題困難。

### UI 風格定調與色彩策略
風格走向定為「專業工具感 + 實驗台」，而不是 marketing 頁。主視覺重點是左側連線控制區與右側結果面板，讓使用者一眼就知道現在是在「設置」、「檢查」、「執行」、「觀察結果」哪個階段。

配色策略：
- 主色：深青藍 `#0f4c5c`，負責主按鈕、標題強調、選取狀態。
- 輔色一：暖灰白 `#f7f4ef`，作為背景與大區塊底色。
- 輔色二：石墨灰 `#21313c`，負責主要文字與深色區塊。
- 強調色：橘紅 `#d95d39`，只用於錯誤、警示與高風險操作。
- 成功色：綠 `#2d6a4f`，只用於 PASS / connected / executed。

### 專案目錄規劃
```text
src/toolanything/
  inspector/
    __init__.py
    app.py              # FastAPI app 與 API route
    service.py          # MCP session / OpenAI 調用核心
    models.py           # request / response model
    static/
      index.html        # UI 結構
      app.js            # 前端互動與 API 呼叫
      styles.css        # 設計 tokens 與元件樣式
tests/
  test_inspector_service.py
docs/
  mcp-test-client-spec.md
```

切分原則：
- `service.py` 僅負責 transport 與 LLM 邏輯，不碰 HTML。
- `app.py` 僅負責 route、input/output 與靜態檔案掛載。
- `static/` 完全獨立，避免引入建置流程。
- 測試只驗 backend service 與 API，不驗瀏覽器像素。

### 前後端模組
- 前端：
  - Connection Form
  - Report Panel
  - Tool Explorer
  - LLM Test Panel
- 後端：
  - Inspector API
  - MCP Session Factory
  - HTTP SSE Session Client
  - STDIO Session Client
  - OpenAI Tool Test Runner

### 模組架構圖（SVG）
```svg
<svg viewBox="0 0 1200 720" xmlns="http://www.w3.org/2000/svg">
  <rect width="1200" height="720" fill="#f7f4ef"/>
  <rect x="60" y="80" width="280" height="180" rx="16" fill="#ffffff" stroke="#0f4c5c" stroke-width="2"/>
  <text x="90" y="130" font-size="28" fill="#21313c">Web UI</text>
  <text x="90" y="175" font-size="18" fill="#21313c">連線設定 / 工具探索</text>
  <text x="90" y="205" font-size="18" fill="#21313c">LLM 測試 / 結果檢視</text>

  <rect x="430" y="80" width="340" height="220" rx="16" fill="#ffffff" stroke="#0f4c5c" stroke-width="2"/>
  <text x="460" y="130" font-size="28" fill="#21313c">Inspector API</text>
  <text x="460" y="175" font-size="18" fill="#21313c">/api/connection/test</text>
  <text x="460" y="205" font-size="18" fill="#21313c">/api/tools/list</text>
  <text x="460" y="235" font-size="18" fill="#21313c">/api/tools/call</text>
  <text x="460" y="265" font-size="18" fill="#21313c">/api/llm/openai/test</text>

  <rect x="860" y="80" width="260" height="140" rx="16" fill="#ffffff" stroke="#2d6a4f" stroke-width="2"/>
  <text x="895" y="130" font-size="28" fill="#21313c">OpenAI API</text>
  <text x="895" y="175" font-size="18" fill="#21313c">Chat Completions</text>

  <rect x="430" y="380" width="300" height="160" rx="16" fill="#ffffff" stroke="#21313c" stroke-width="2"/>
  <text x="460" y="430" font-size="26" fill="#21313c">MCP Session Service</text>
  <text x="460" y="470" font-size="18" fill="#21313c">HTTP SSE Session</text>
  <text x="460" y="500" font-size="18" fill="#21313c">STDIO Session</text>

  <rect x="840" y="360" width="300" height="90" rx="16" fill="#ffffff" stroke="#0f4c5c" stroke-width="2"/>
  <text x="875" y="415" font-size="26" fill="#21313c">MCP HTTP Server</text>
  <rect x="840" y="500" width="300" height="90" rx="16" fill="#ffffff" stroke="#0f4c5c" stroke-width="2"/>
  <text x="905" y="555" font-size="26" fill="#21313c">MCP STDIO Server</text>

  <line x1="340" y1="170" x2="430" y2="170" stroke="#0f4c5c" stroke-width="4"/>
  <line x1="770" y1="170" x2="860" y2="170" stroke="#2d6a4f" stroke-width="4"/>
  <line x1="600" y1="300" x2="600" y2="380" stroke="#21313c" stroke-width="4"/>
  <line x1="730" y1="430" x2="840" y2="405" stroke="#0f4c5c" stroke-width="4"/>
  <line x1="730" y1="500" x2="840" y2="545" stroke="#0f4c5c" stroke-width="4"/>
</svg>
```

### 使用流程
- 新使用者：選 transport → 填 URL/command → 檢查連線 → 載入工具 → 手動呼叫。
- 進階使用者：在同一頁填 API key + model + prompt → 執行 LLM 測試。
- 若要重做：按「重新開始」清空表單、結果與 localStorage 中的暫存設定。

### 功能清單（含 CRUD 與 state）
| 功能 | Create | Update | Delete | 主要狀態 |
|---|---|---|---|---|
| 連線設定 | 建立 transport config | 修改 URL/command/user_id/model | 清空本地暫存 | idle / validating / valid / failed |
| 工具探索 | 取得 tools list | 切換選定工具與參數 | 清空本次工具結果 | idle / loading / ready / error |
| 手動工具呼叫 | 建立一次 call request | 修改參數後重送 | 清空結果 | idle / running / success / error |
| LLM 測試 | 建立一次 prompt run | 修改 prompt/model 後重跑 | 清空 transcript | idle / planning / calling_tool / completed / error |

### G3M
- Goal：提供正式內建 client 測試 MCP server 與 LLM tool-calling。
- Gain：降低使用者除錯成本，補齊 repo 產品完整度。
- Metric：
  - 內建 UI 能完成 stdio / HTTP roundtrip。
  - LLM 測試能在至少一個 sample server 上成功產生 tool call。
  - 全量測試通過。

### UI 設計
採雙欄布局：左欄是設定與操作，右欄是結果與記錄。畫面一次只保留一個主要焦點：如果還沒連線，焦點是連線卡；如果已載入工具，焦點轉到工具探索；如果在跑 LLM 測試，焦點轉到 transcript 面板。

主要操作必須保持在首屏可見，不依賴長頁面向下捲動。結果區以 tabs 分為「診斷報告」、「工具結果」、「LLM transcript」三塊，避免資訊互相干擾。

### UI 元件清單
| 元件 | 用途 | 關鍵屬性 | 互動方式 |
|---|---|---|---|
| TransportSelect | 選 transport | mode | 切換時動態切換欄位 |
| ConnectionForm | URL/command/user_id/model | url, command, user_id | 輸入後可檢查連線或載入工具 |
| ReportCard | 顯示診斷步驟 | step name, status, duration | 純展示 |
| ToolPicker | 選工具 | selected tool | 連動 schema form |
| ArgumentForm | 產生參數輸入 | schema properties | 送出工具呼叫 |
| JsonViewer | 顯示工具結果 | payload | 支援複製 |
| LlmPromptForm | 填 API key/model/prompt | api_key, model, prompt | 執行 LLM 測試 |
| TranscriptTimeline | 顯示 tool trace | assistant/tool/error entries | 垂直時間線 |
| ResetButton | 清空暫存 | none | 重置 localStorage + UI state |

### 分步導覽策略
本功能不採 wizard，而採單頁分段 + tabs。原因是使用者需要來回調整 transport、工具參數與 prompt，wizard 會使探索成本過高；單頁分段更符合「測試台」心智模型。

### 主要畫面示意（SVG）
```svg
<svg viewBox="0 0 1440 960" xmlns="http://www.w3.org/2000/svg">
  <rect width="1440" height="960" fill="#f7f4ef"/>
  <rect x="40" y="40" width="420" height="880" rx="24" fill="#ffffff" stroke="#d6d0c4"/>
  <text x="80" y="100" font-size="36" fill="#21313c">MCP Test Client</text>
  <rect x="70" y="140" width="360" height="220" rx="16" fill="#fbfaf7" stroke="#0f4c5c"/>
  <text x="95" y="185" font-size="24" fill="#21313c">連線設定</text>
  <text x="95" y="225" font-size="18" fill="#21313c">transport / URL 或 command / user_id</text>
  <text x="95" y="255" font-size="18" fill="#21313c">檢查連線 / 載入工具 / 重新開始</text>

  <rect x="70" y="390" width="360" height="230" rx="16" fill="#fbfaf7" stroke="#21313c"/>
  <text x="95" y="435" font-size="24" fill="#21313c">工具探索</text>
  <text x="95" y="475" font-size="18" fill="#21313c">工具清單 / 參數表單 / 執行按鈕</text>

  <rect x="70" y="650" width="360" height="230" rx="16" fill="#fbfaf7" stroke="#2d6a4f"/>
  <text x="95" y="695" font-size="24" fill="#21313c">LLM 測試</text>
  <text x="95" y="735" font-size="18" fill="#21313c">API key / model / prompt / 執行</text>

  <rect x="500" y="40" width="900" height="880" rx="24" fill="#ffffff" stroke="#d6d0c4"/>
  <text x="550" y="100" font-size="34" fill="#21313c">結果面板</text>
  <rect x="540" y="140" width="820" height="70" rx="14" fill="#0f4c5c"/>
  <text x="580" y="185" font-size="22" fill="#ffffff">診斷報告 / 工具結果 / LLM transcript tabs</text>
  <rect x="540" y="240" width="820" height="620" rx="18" fill="#fbfaf7" stroke="#d6d0c4"/>
  <text x="580" y="300" font-size="22" fill="#21313c">依目前操作顯示步驟、JSON 結果與 tool traces</text>
</svg>
```

### 非功能需求
- 效能：單次連線測試應在 10 秒內完成或明確 timeout。
- 可靠性：每個 API request 使用獨立 session，避免殘留壞狀態。
- 安全性：OpenAI API key 只走 backend，不落盤；前端只保存在記憶體。
- 可用性：所有主要操作在首屏可見；錯誤需顯示 transport、步驟與建議。
- 可維護性：service 邏輯與 UI 靜態資產分離，避免跨層耦合。

### 核心資料模型
| 實體 | 主要欄位 | 說明 |
|---|---|---|
| InspectorTargetConfig | mode, url, command, user_id | 測試目標設定 |
| ConnectionReport | mode, ok, steps, duration_ms | 連線測試結果 |
| ToolEntry | name, description, input_schema | 工具清單項目 |
| ToolCallResult | result, raw_result, meta | 單次工具呼叫結果 |
| LlmRunTranscript | prompt, model, rounds, entries | 一次 LLM 測試紀錄 |

### State 管理與持久化
- 前端暫存：
  - transport mode
  - URL / command
  - user_id
  - model
- 持久化方式：`localStorage`
- 不持久化：
  - OpenAI API key
  - 工具執行結果
  - transcript
- 恢復流程：頁面載入時自動讀取本地設定，填回表單。
- 重新開始：清空本地設定與當前 UI state。

### API 設計
| Endpoint | 方法 | 用途 |
|---|---|---|
| `/api/health` | GET | UI health |
| `/api/connection/test` | POST | 執行 roundtrip 診斷 |
| `/api/tools/list` | POST | 取得工具清單 |
| `/api/tools/call` | POST | 手動呼叫工具 |
| `/api/llm/openai/test` | POST | 執行 OpenAI tool-calling 測試 |

主要輸入格式：
- `InspectorTargetConfig`
  - `mode`: `http` or `stdio`
  - `url`: HTTP base URL
  - `command`: stdio command string
  - `user_id`: optional

### 錯誤處理 / 回退策略 / 可觀測性
- 所有 API 回傳 JSON 錯誤格式：
  - `error.type`
  - `error.message`
  - `error.details`
- 連線失敗時顯示：
  - 發生在哪一個步驟
  - 原始例外摘要
  - 建議處置
- LLM 測試失敗時顯示：
  - OpenAI request 失敗
  - 模型未產生 tool call
  - tool args 非合法 JSON
- logs：
  - inspector request start/end
  - transport mode
  - timeout / failure category
- metrics/traces 本次不做獨立實作，但保留 logger hook。

### 狀態機
| 狀態 | 事件 | 下一狀態 |
|---|---|---|
| idle | submit connection test | validating |
| validating | all steps pass | valid |
| validating | any step fail | failed |
| valid | load tools | loading_tools |
| loading_tools | tools returned | tools_ready |
| tools_ready | call tool | calling_tool |
| calling_tool | call success | tool_success |
| calling_tool | call fail | tool_error |
| tools_ready | start llm run | llm_running |
| llm_running | llm completes | llm_success |
| llm_running | llm/tool fail | llm_error |

### 通知與背景執行
本次不做背景 queue。所有操作都以同步 request 完成，但前端要有 loading 與 timeout 提示。未來若要支援長流程 transcript streaming，可把 LLM run 抽成背景任務並用 SSE 回傳。

### UI 事件回報
| 事件 | 觸發時機 | 欄位 |
|---|---|---|
| `inspect_connection_submitted` | 點檢查連線 | mode |
| `inspect_tools_loaded` | tools/list 成功 | mode, tool_count |
| `inspect_tool_called` | 手動呼叫成功 | mode, tool_name |
| `inspect_llm_test_started` | 點 LLM 測試 | mode, model |
| `inspect_llm_test_finished` | LLM 測試完成 | mode, model, tool_calls |

### UI ↔ API Mapping
| UI 區塊 | API | 預期結果 |
|---|---|---|
| 檢查連線按鈕 | `/api/connection/test` | 報告卡片更新 |
| 載入工具按鈕 | `/api/tools/list` | 工具下拉與 schema form 更新 |
| 執行工具按鈕 | `/api/tools/call` | JSON viewer 更新 |
| 執行 LLM 測試按鈕 | `/api/llm/openai/test` | transcript panel 更新 |

### UI 狀態保存與重新開始
- 保存：
  - mode, url, command, user_id, model
- 不保存：
  - api key
  - JSON result
  - transcript
- 重新開始：
  - 清空 localStorage
  - 清空報告、工具列表、參數值與 transcript

### 建議補充的功能
- raw JSON-RPC viewer
- resources/prompts explorer
- 匯出測試報告 JSON
- multi-provider LLM test
- streamable HTTP transport 支援

### 驗收條件
- `toolanything inspect` 可啟動本地 Web UI。
- 使用者可在 UI 中完成 stdio 與 HTTP 的基本連線測試。
- 使用者可載入工具並手動呼叫工具。
- 使用者提供 OpenAI API key 與 model 後，可完成至少一輪 tool-calling 測試。
- 本 repo 全量測試通過。

### 測試案例
- HTTP MCP sample server：initialize / tools/list / tools/call 成功。
- stdio sample server：initialize / tools/list / tools/call 成功。
- tool schema 轉 OpenAI tools 成功。
- OpenAI tool run 在 mock response 下可走完至少一輪 tool call。
- UI config localStorage restore/clear 行為正確。

### Edge / Abuse cases
- URL 為空。
- stdio command 為空。
- server 沒有可呼叫工具。
- tool args 不是合法 JSON。
- OpenAI API key 無效。
- 模型沒有回傳 tool call。
- tool call arguments 不是 JSON 字串。
- tools/list 成功但 tools/call timeout。

### 風險與未決事項
- 目前 HTTP transport 仍以 SSE 為主，未覆蓋未來可能的 Streamable HTTP。
- OpenAI tool-calling 測試使用通用 OpenAI tools 轉換，驗證的是「模型能否調用工具」，不是「Remote MCP 直連 OpenAI」。
- stdio 模式的跨 request 狀態不保證持續，因此複雜 stateful flow 不屬於 v1 承諾。

## 非技術規格文件

### 這份規格是寫給誰看的
這份說明是寫給想確認「我的工具服務到底有沒有接通」的人。你不用先安裝別的除錯工具，也不用自己手打一堆測試指令。

### 這個工具能做什麼
它會提供一個內建測試頁面，讓你填入連線方式、位置與執行指令，快速檢查工具服務是否真的有回應。你也可以直接在畫面上挑選工具、填入參數、看到回傳結果。

如果你有 OpenAI 的金鑰與模型名稱，還可以進一步測試模型會不會真的挑對工具並執行。

### 你會怎麼使用它
1. 啟動 `toolanything inspect`。
2. 在畫面左邊選擇你要測的是網址連線還是本機指令。
3. 輸入連線資訊後，按「檢查連線」。
4. 確認通過後，按「載入工具」。
5. 選一個工具，填好參數，按「執行工具」。
6. 如果要測模型，填上金鑰、模型名稱和一句任務描述，再按「執行 LLM 測試」。

### 你會看到哪些主要畫面
- 連線設定區：填寫網址、執行指令、使用者代號。
- 工具區：看到所有可用工具，並直接填參數執行。
- 結果區：顯示每一步有沒有成功，以及工具真正回了什麼。
- 模型測試區：顯示模型說了什麼、挑了哪個工具、工具回了什麼。

### 畫面風格與色彩
畫面會偏向專業測試台風格，不會像宣傳頁。底色偏暖白，主操作用深青藍，成功用綠色，錯誤用橘紅色，讓你很快分辨目前狀態。

### 畫面示意（SVG）
```svg
<svg viewBox="0 0 1440 960" xmlns="http://www.w3.org/2000/svg">
  <rect width="1440" height="960" fill="#f7f4ef"/>
  <rect x="50" y="50" width="420" height="860" rx="24" fill="#ffffff" stroke="#d6d0c4"/>
  <text x="90" y="110" font-size="34" fill="#21313c">測試設定</text>
  <text x="90" y="170" font-size="20" fill="#21313c">選連線方式、填網址或指令</text>
  <text x="90" y="220" font-size="20" fill="#21313c">按檢查連線 / 載入工具</text>
  <text x="90" y="300" font-size="20" fill="#21313c">挑工具、填參數、執行</text>
  <text x="90" y="390" font-size="20" fill="#21313c">填模型測試資料</text>

  <rect x="510" y="50" width="880" height="860" rx="24" fill="#ffffff" stroke="#d6d0c4"/>
  <text x="560" y="110" font-size="34" fill="#21313c">結果與紀錄</text>
  <text x="560" y="170" font-size="20" fill="#21313c">這裡會顯示檢查結果、工具輸出與模型調用過程</text>
</svg>
```

### 操作流程
先確認連線有沒有通，再去看工具清單，最後才測模型。這樣你才分得出來是服務沒接通，還是模型不會挑工具。

### 你會看到的提示語
- 成功：
  - `連線成功，已完成 initialize 與 tools/list`
  - `工具執行完成`
  - `LLM 已成功發起工具呼叫`
- 失敗：
  - `連線失敗，請確認 URL 或 command`
  - `找不到可呼叫工具`
  - `模型未產生工具呼叫`
  - `工具參數格式錯誤`
- 等待中：
  - `正在檢查連線...`
  - `正在載入工具...`
  - `正在等待模型回應...`

### 限制與注意事項
- 這是測試工具，不是正式聊天介面。
- 模型測試需要你自己提供金鑰與模型名稱。
- 某些需要長時間保存現場狀態的工具流程，不屬於這個版本的保證範圍。

### 成功完成後會得到什麼
你會知道：
- 服務有沒有真的接通
- 工具有沒有列出來
- 工具能不能真的被呼叫
- 模型會不會挑對工具

### 常見問題與錯誤提示
- 如果連線一直失敗，先檢查服務是不是已經啟動。
- 如果工具清單是空的，代表目前服務沒有提供可用工具。
- 如果模型沒有調工具，不一定是服務壞了，也可能是提示語太模糊。

## Web 版 Codex 分階段開發計畫

### Stage 0：建立 Inspector 骨架
- 目標：建立 inspector 模組、CLI 入口與靜態資產掛載。
- 前置條件：現有 CLI / FastAPI 可正常使用。
- Codex Web Instructions
```text
[任務範圍]
建立內建 Web 版 MCP Test Client 的基本骨架，不實作完整 transport 與 LLM 邏輯。

[需修改/新增的檔案清單]
src/toolanything/cli.py
src/toolanything/inspector/__init__.py
src/toolanything/inspector/app.py
src/toolanything/inspector/static/index.html
src/toolanything/inspector/static/app.js
src/toolanything/inspector/static/styles.css

[具體步驟]
1. 新增 inspect 子命令。
2. 建立 FastAPI app 並掛載 static。
3. 建立首頁與 /api/health。
4. 讓 UI 可成功載入並顯示基礎版面。

[輸出格式要求]
可直接執行的程式碼與最小文件更新。

[測試要求]
新增 API smoke test，確認 / 與 /api/health 可用。

[驗收標準 DoD]
執行 inspect 後可在瀏覽器開到 UI，且 health API 回 200。
```
- 風險與回滾方式：若 inspector app 影響現有 CLI，可先回滾 inspect 子命令與新模組。

### Stage 1：實作通用 MCP Session Service
- 目標：支援 stdio 與 HTTP SSE 的 initialize/tools/list/tools/call。
- 前置條件：Stage 0 完成。
- Codex Web Instructions
```text
[任務範圍]
建立 backend service，封裝短生命週期 MCP session。

[需修改/新增的檔案清單]
src/toolanything/inspector/service.py
src/toolanything/inspector/models.py
tests/test_inspector_service.py

[具體步驟]
1. 建立 target config model。
2. 建立 stdio session client。
3. 建立 HTTP SSE session client。
4. 實作 test_connection/list_tools/call_tool。
5. 加入 timeout 與錯誤正規化。

[輸出格式要求]
service 與 model 分離，避免把 transport 邏輯寫進 route。

[測試要求]
以本 repo sample server 驗證 stdio 與 http roundtrip。

[驗收標準 DoD]
service 可通過 initialize/tools/list/tools/call 測試。
```
- 風險與回滾方式：若 session service 設計過重，可退回 stateless function，但不能把協議邏輯散回 route。

### Stage 2：完成連線測試與工具探索 UI
- 目標：讓使用者可透過 UI 完成連線測試、載入工具、手動呼叫工具。
- 前置條件：Stage 1 完成。
- Codex Web Instructions
```text
[任務範圍]
做完整可用的 Web UI，不引入前端建置工具。

[需修改/新增的檔案清單]
src/toolanything/inspector/app.py
src/toolanything/inspector/static/index.html
src/toolanything/inspector/static/app.js
src/toolanything/inspector/static/styles.css

[具體步驟]
1. 新增 /api/connection/test、/api/tools/list、/api/tools/call。
2. 前端建立 transport form、報告卡、工具選擇器、參數表單。
3. 依 JSON schema 產生基本欄位。
4. 顯示 JSON result 與錯誤訊息。
5. 加入 localStorage 設定保存與重新開始。

[輸出格式要求]
介面需為淺色模式、雙欄布局、首屏可完成主要操作。

[測試要求]
API 測試 + schema form 的基本互動測試（若不做瀏覽器自動化，至少測 backend 契約）。

[驗收標準 DoD]
使用者可在 UI 中完成連線測試、載入工具、手動呼叫工具。
```
- 風險與回滾方式：若 schema form 太複雜，可先降級為 JSON textarea，但要保留未來擴充點。

### Stage 3：加入 OpenAI LLM 工具調用測試
- 目標：讓使用者輸入 API key、model、prompt 後，驗證模型是否會調工具。
- 前置條件：Stage 2 完成。
- Codex Web Instructions
```text
[任務範圍]
加入可選的 OpenAI tool-calling smoke test。

[需修改/新增的檔案清單]
src/toolanything/inspector/service.py
src/toolanything/inspector/app.py
src/toolanything/inspector/static/index.html
src/toolanything/inspector/static/app.js
tests/test_inspector_service.py

[具體步驟]
1. 將 MCP tools/list 結果轉成 OpenAI tools。
2. 建立 OpenAI chat completion request。
3. 處理 tool_calls 與 tools/call 回圈。
4. 回傳 transcript、tool traces、final answer。
5. 前端顯示模型推理軌跡與錯誤。

[輸出格式要求]
API key 不可持久化；只存在單次 request 記憶體中。

[測試要求]
以 mock OpenAI response 驗證至少一輪 tool call。

[驗收標準 DoD]
在 mock 與實機條件下，LLM 測試都能輸出可讀 transcript。
```
- 風險與回滾方式：若 OpenAI loop 複雜度過高，可先限制單輪 tool call，但必須清楚標示限制。

### Stage 4：補齊整合測試 / 回歸測試 / 邊界測試
- 目標：補足 timeout、空工具清單、參數錯誤、OpenAI 錯誤等情境。
- 前置條件：Stage 3 完成。
- Codex Web Instructions
```text
[任務範圍]
補回歸與邊界測試，確保 inspect 功能可維護。

[需修改/新增的檔案清單]
tests/test_inspector_service.py
tests/test_cli.py
tests/test_mcp_server_integration.py

[具體步驟]
1. 補 stdio/http failure cases。
2. 補 tool args invalid JSON。
3. 補 OpenAI invalid key / no tool call / malformed arguments。
4. 驗證 CLI inspect 啟動與 API smoke test。

[輸出格式要求]
測試案例名稱需清楚描述 transport 與情境。

[測試要求]
跑全量 pytest。

[驗收標準 DoD]
新功能的正常與異常路徑都有測試保護。
```
- 風險與回滾方式：若測試依賴過高，先保留 mock-based tests，不強求外部網路整合測試進 CI。

### Stage 5：文件化與交付
- 目標：補齊 README 與 examples 導航，讓使用者知道怎麼用 inspect。
- 前置條件：Stage 4 完成。
- Codex Web Instructions
```text
[任務範圍]
完成 inspect 相關文件與使用說明。

[需修改/新增的檔案清單]
README.md
docs/docs-map.md
examples/README.md

[具體步驟]
1. 補 inspect 啟動方式。
2. 補 transport 模式說明。
3. 補 user_id / OpenAI 測試限制。
4. 補與 doctor 的定位差異。

[輸出格式要求]
文件需明確說明 v1 限制，不可暗示支援桌面或完整官方 inspector 功能。

[測試要求]
確認 README 指令與實際 CLI 一致。

[驗收標準 DoD]
新使用者只靠 README 就能啟動 inspect 並完成基本測試。
```
- 風險與回滾方式：若文件落後於實作，寧可先補限制說明，也不要寫過度承諾。
