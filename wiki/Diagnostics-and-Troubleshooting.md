# Diagnostics and Troubleshooting

這是一份 runbook 風格文件，重點是讓你在 transport、module 載入、tool call 或 OpenAI roundtrip 出問題時，知道先檢查什麼。

## 最先該做的事

優先順序：

1. 跑 `toolanything doctor`
2. 必要時開 `toolanything inspect`
3. 再去看 `logs/toolanything.log`

## `doctor` 能檢查什麼

- stdio 或 HTTP transport 是否可連
- initialize 是否成功
- `tools/list` 是否成功
- `tools/call` 是否成功
- 是否屬於參數衝突或啟動設定錯誤

## 常見症狀與處理

### 症狀：`ModuleNotFoundError: No module named 'toolanything'`

原因：

- 尚未安裝套件
- 或目前 shell 沒拿到正確虛擬環境

處理：

```bash
pip install -e .
```

### 症狀：找不到工具模組檔案

原因：

- `serve` 收到的是檔案路徑，但你不在 repo root
- 或路徑本身不存在

處理：

- 改用絕對路徑
- 或切回 repo root 再執行
- 若你本來想傳模組路徑，請改成 `examples.quickstart.tools` 這類形式

### 症狀：HTTP server 未就緒

通常來自兩種問題：

- 啟動命令有誤
- 依賴或程式啟動時例外導致 server 沒起來

先做：

1. 檢查 `doctor` 的 `stderr`
2. 直接手動執行同一條 `serve` 命令
3. 看 `logs/toolanything.log`

若是部署環境中的 alert 或健康檢查失敗，也應優先確認是不是 server 根本沒起來，而不是直接懷疑 MCP protocol 本身。

### 症狀：HTTP client 可打到 base URL，但 MCP 呼叫失敗

原因可能是：

- 你把 legacy server 當成 `/mcp` server 在打
- Streamable HTTP 少帶 `Mcp-Session-Id` 或 `MCP-Protocol-Version`
- 你跳過了 `initialize`

處理：

- 確認 transport 類型
- 確認 Streamable HTTP 已先建 session
- 用 `examples/streamable_http/` 對照你的 client 行為

### 症狀：Web UI 連得到 server，但瀏覽器端請求被擋

原因通常是 CORS。

處理：

```powershell
$env:TOOLANYTHING_ALLOWED_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
```

### 症狀：OpenAI runtime 直接報缺少 API key

原因：

- `OPENAI_API_KEY` 未設定
- 或你自訂了 `api_key_env` 卻沒提供對應環境變數

處理：

- 設定 `OPENAI_API_KEY`
- 或在 `OpenAIChatRuntime(..., api_key_env="...")` 中改用正確名稱

### 症狀：同步 API 在事件迴圈中報錯

原因：

- 你在已運行的事件迴圈內呼叫 `run(...)`、`execute_tool_call(...)` 之類同步包裝器

處理：

- 改用 `run_async(...)`
- 或改用 `invoke_tool_call(...)`

## Remediation

當你不確定該先修哪裡時，通用的 remediation 順序是：

1. 先用最小命令重現
2. 縮小成單一 transport 或單一工具
3. 確認 registry 內是否真的有該工具
4. 再決定是修 tool、修 transport 還是修 host 設定

如果修復造成整體整合更不穩，應先 rollback 到最近可用的 transport / tool 設定，再逐步加回變更。

## Verify

每次修完都要 verify 至少一件事：`doctor` 是否恢復正常，或 `inspect` / 真實 host 是否已能再次成功完成 `tools/list` 與 `tools/call`。

## 除錯建議順序

### MCP transport 問題

1. 先用 `doctor`
2. 再用 `inspect`
3. 最後對照 `examples/mcp_transports/` 或 `examples/streamable_http/`

### 工具註冊或搜尋問題

1. 跑 `toolanything search`
2. 確認工具名稱、tags、metadata 是否如預期
3. 再檢查是不是註冊在錯的 registry

### OpenAI tool loop 問題

1. 先呼叫 `to_schema()` 看工具是否有正確匯出
2. 再檢查 API key、model 名稱與 `max_rounds`
3. 最後看 `transcript`

## 什麼時候要停止自行處理

## Escalation

如果你已確認：

- `doctor` 與 `inspect` 都顯示異常
- 同一組工具在最小範例可運作，但在你的整合環境才失敗
- 錯誤與 session、代理、網路拓撲或 host 實作高度相關

那就不該再只修本地工具層，應回頭檢查 host、proxy 或部署環境。

在這種情況下，驗證重點不再只是 `tools/list` 有沒有成功，而是整條請求路徑是否在正確的網路與 session 邊界內。

## 相關文件

- [CLI Reference](CLI-Reference)
- [MCP Serving and Transports](MCP-Serving-and-Transports)
- [OpenAI Tool Calling](OpenAI-Tool-Calling)
