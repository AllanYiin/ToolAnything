# Custom MCP Server Policy

## 目的

這份規範只處理一件事：讓 agent 自訂工具長期落在同一個可維運的 MCP server，而不是每次生一支新工具就多一個新 server。

## Canonical server root

單機只允許一個 canonical 自訂工具專用 server root：

- Windows：`%USERPROFILE%\\.toolanything\\agent-mcp\\`
- macOS / Linux：`~/.toolanything/agent-mcp/`

建議結構：

```text
agent-mcp/
  server.py
  toolanything-server.json
  tools/
  logs/
```

## Transport 與 port

1. 這個共用 server 預設用 `streamable-http`。
2. host 固定 `127.0.0.1`。
3. port 固定 `9092`。
4. 若 `9092` 被占用，先回報衝突；不要靜默切到隨機 port。

原因：

1. 單一固定 port 才能配合桌面 host、檢查腳本與自動啟動設定。
2. `toolanything` CLI 本身已把 `run-streamable-http` 的預設 port 設為 `9092`。
3. 對 ToolAnything wrapper 這種長期共用 server 而言，固定 endpoint 比臨時 process 更容易維運。

## 何時仍可先用 stdio

若只是做一次性驗證、桌面 host 子程序直連、或還在開發最小 proof-of-concept，可以先用 `stdio` 驗證工具正確性；但只要要進入「可重複安裝、重開機自動恢復、被多個 agent 任務重用」的狀態，就必須回到這份共用 server 規範。

## 自動啟動

### Windows

- 用 Task Scheduler 建立開機或登入後自動啟動的 task。
- 啟動命令固定為：

```powershell
python -m toolanything.cli serve %USERPROFILE%\\.toolanything\\agent-mcp\\server.py --streamable-http --host 127.0.0.1 --port 9092
```

### Linux

- 用 `systemd --user` service。
- service 應在登入後自動啟動，並在失敗時自動重試。

### macOS

- 用 `LaunchAgent`。
- 啟動命令固定指向同一份 `server.py`。

## 新工具整合規則

1. 新工具模組新增到 `tools/`。
2. 共用 `server.py` 負責載入這些模組或統一註冊 registry。
3. 不允許因為單一工具需求就複製一份新的 `server.py` 再跑第二個常駐 server。
4. 只有不同信任邊界、不同 runtime、或不同維運責任人才可例外拆分。

## 最小驗證

1. `http://127.0.0.1:9092/health` 回應 200。
2. `/mcp` `tools/list` 看得到新工具。
3. 系統重啟或重新登入後 server 會自動恢復。
