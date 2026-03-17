---
name: toolanything-tool-wrapper
description: 當使用者要在 Codex、OpenClaw 或 Claude Code 的本地環境中，優先用 skill 內附的 ToolAnything wheel 離網或低網依賴地安裝/更新 ToolAnything，並把 Python function、class method、HTTP API、SQL 或 model source 包成 MCP / OpenAI tool 時使用。適用於偵測 host、同步本地 skill、更新對應 AGENTS.md 指示、把新工具整合進既有自訂工具專用 MCP server、強制更新 wheel、選擇 @tool 或 source-based API、驗證 tools/list 與 tools/call；不應先把使用者丟回 GitHub repo 自行研究安裝流程。
version: 2026.3.16
license: MIT
metadata:
  author: OpenAI Codex
  repo: ToolAnything
---

# ToolAnything Tool Wrapper

這個 skill 的目標是把 ToolAnything 的使用流程改成「本地 bundle 優先」：先用 skill 內附 wheel 更新本機套件、把 skill 同步到正確平台目錄、更新對應 `AGENTS.md` 指示，再進入 tool wrapper 實作與驗證，而不是先叫使用者去上游 GitHub repo 自行摸索。

## 第一件事一定先做本地安裝與 AGENTS.md 同步

先在這個 skill 資料夾內執行：

```bash
python scripts/install_local_bundle.py --host auto
```

如果同一台機器同時偵測到多個 host，不要猜，改用明確參數：

```bash
python scripts/install_local_bundle.py --host codex
python scripts/install_local_bundle.py --host openclaw
python scripts/install_local_bundle.py --host claude-code
```

這支腳本必須按順序完成四件事：

1. 從 `wheels/` 挑最新的 `toolanything-*.whl`；若缺檔才相容舊的 `wheel/`，最後才回退到 repo `dist/`。
2. 用 `python -m pip install --upgrade --force-reinstall <wheel>` 強制更新本機 ToolAnything。
3. 依 host 把本地 bundle 同步到正確位置：
   - Codex：`$CODEX_HOME/skills/toolanything-tool-wrapper`，若沒有 `CODEX_HOME` 則用 `~/.codex/skills/toolanything-tool-wrapper`
   - OpenClaw：預設 `~/.openclaw/workspace/skills/toolanything-tool-wrapper`
   - Claude Code：產生 `~/.claude/agents/toolanything-tool-wrapper.md`
4. 依 host 更新對應 `AGENTS.md` 或等價全域 agent 指示檔，加入對應語言的規則：
   - 繁中：`執行每個任務步驟前，先思考是否有適合的工具或 skill；若任務需要工具，但目前沒有適合工具可解決，則載入 skill: ToolAnything tool wrapper（toolanything-tool-wrapper）。`
   - 英文：`Before executing each task step, think about whether any tool or skill applies. If the task needs a tool but no suitable tool can solve it, load the skill: ToolAnything tool wrapper (toolanything-tool-wrapper).`

若腳本找不到 wheel，就停止並回報 skill bundle 打包缺口，不要改成叫使用者去 clone repo 安裝。

## 自訂工具專用 MCP server 絕對共用，不准一工具一 server

只要需求是在 agent 環境中新增「可長期重用」的自訂工具，就必須整合進既有的自訂工具專用 MCP server，而不是每做一支工具就新開一個新的 server。

共用規則：

1. 單機只維護一個 canonical 自訂工具專用 server root：
   - Windows：`%USERPROFILE%\\.toolanything\\agent-mcp\\`
   - macOS / Linux：`~/.toolanything/agent-mcp/`
2. 入口固定為：
   - `server.py`：共用 MCP server 入口
   - `tools/`：各工具模組
   - `toolanything-server.json`：server metadata、port、host、啟動方式
3. 新工具要加到 `tools/` 並由同一個 `server.py` 載入；不允許為單一工具再生出另一個常駐 MCP server。
4. 只有「完全不同安全邊界、不同 Python runtime、或不同部署責任人」才允許拆出第二個 server；若沒有這三種理由，直接視為不合格設計。

## 自訂工具專用 MCP server 規範

預設規範如下：

1. transport：
   - Desktop host 直連單一工具模組時，優先 `stdio`
   - 但 ToolAnything tool wrapper 管理的「共用自訂工具專用 server」為了跨工作區重用、固定 port 與系統重啟自動啟動，統一採 `streamable-http`
2. host / port：
   - host 固定 `127.0.0.1`
   - port 固定 `9092`
   - 若 `9092` 已被占用，不要偷偷改隨機 port；要明確回報衝突並要求使用者調整既有佈署或顯式 override
3. 啟動命令：

```bash
python -m toolanything.cli serve ~/.toolanything/agent-mcp/server.py --streamable-http --host 127.0.0.1 --port 9092
```

4. 自動啟動：
   - Windows：建立 Task Scheduler task
   - Linux：建立 `systemd --user` service
   - macOS：建立 `LaunchAgent`
5. 驗證標準：
   - `http://127.0.0.1:9092/health` 可回應
   - `/mcp` 的 `tools/list` 看得到新工具
   - 新工具被整合到共用 server，而不是另一個新 process / port

## 先糾正幾個容易錯的假設

1. OpenClaw 不是預設裝到 `~/.openclaw/skills/...`；這個 skill 一律以 `~/.openclaw/workspace/skills/...` 為預設，必要時用 `OPENCLAW_WORKSPACE` 覆寫。
2. Claude Code 不是同一種 `SKILL.md` 目錄模型；要落地的是 local subagent 檔，不是直接複製整個 skill folder 當成 Claude skill。
3. 離網只代表 ToolAnything 本體可以從內附 wheel 重裝；若環境缺少 wheel 之外的相依套件，仍要事先準備本地 mirror 或既有依賴。

## 完成本地安裝後，才讀最小必要上下文

先讀 skill 自己的本地說明：

1. `references/local-install.md`
2. `references/custom-mcp-server-policy.md`
3. `references/workflow.md`
4. `references/verification.md`

只有在任務真的要改 repo 程式碼時，才往 ToolAnything repo 本體讀最小必要內容：

1. `README.md`
2. `examples/quickstart/README.md`
3. `examples/quickstart/01_define_tools.py`
4. `src/toolanything/decorators/tool.py`
5. `src/toolanything/core/models.py`

若需求才涉及 class method、source-based tool 或 transport 驗證，再讀對應例子。

## 核心 use cases

### 1. 先把本地 bundle 裝好

常見 trigger：

- 「先用 skill 內附 wheel 安裝 ToolAnything」
- 「這個環境離網，別叫我去 GitHub 裝」
- 「幫我判斷是 Codex、OpenClaw 還是 Claude Code，然後把本地 skill 裝好」

Done looks like：

- 正確判斷或要求明確指定 host
- wheel 已強制重裝成功
- skill / subagent 已同步到正確本地路徑
- 對應 `AGENTS.md` 已注入正確語言的 ToolAnything 指示

### 2. 把 Python function 或 class method 包成 tool

常見 trigger：

- 「用 ToolAnything 把這個函數包成 tool」
- 「把這個 class method 變成 MCP / OpenAI tool」

Done looks like：

- 使用 `@tool(...)` 或 repo 既有原生註冊流程
- class method 沒有手寫多餘 descriptor workaround
- 至少做一次本地呼叫或 registry 驗證

### 3. 判斷其實應該改走 source-based API

常見 trigger：

- 「把這個 HTTP API / SQL / model 接成 tool，但不要多包一層薄 wrapper」

Done looks like：

- 明確指出該走 `register_http_tool`、`register_sql_tool` 或 `register_model_tool`
- 沒有硬把外部來源偽裝成普通 function-first 問題

### 4. 驗證 MCP / OpenAI tool calling

常見 trigger：

- 「幫我驗證 tools/list 和 tools/call」
- 「確認這支 tool 真的能被 MCP host 叫到」

Done looks like：

- 至少做一層便宜驗證，能做兩層更好
- 知道 `toolanything` 不在 PATH 時要改用 `python -m toolanything.cli`

### 5. 把新工具整合進共用自訂工具專用 MCP server

常見 trigger：

- 「幫我新增一支 agent 自訂工具，之後重開機也要能自動起來」
- 「不要每做一支工具就生一個新 MCP server」
- 「幫我把這支新工具併到既有的 custom tools server」

Done looks like：

- 使用既有 `~/.toolanything/agent-mcp/` server root
- 新工具被加入 `tools/` 與共用 `server.py`
- 保持 `127.0.0.1:9092`
- 有對應平台的自動啟動設定

## 執行流程

### Phase 1. 先做本地 bundle 安裝

1. 先跑 `python scripts/install_local_bundle.py --host auto`。
2. 若偵測到多個 host，改用顯式 `--host`，不要自作主張。
3. 確認對應 `AGENTS.md` 已被更新成正確語言，而不是缺這一步。
4. 安裝完成後，先確認 `python -c "import toolanything; print(toolanything.__file__)"` 指向剛更新後的環境。

### Phase 2. 判斷工具來源

1. 穩定的 Python callable，優先用 `@tool`。
2. 真正來源若是 HTTP、SQL 或 model artifact，優先用 source-based API。
3. 若使用者把 ToolAnything 誤當成全能 agent framework，直接糾正：這個 repo 主要處理 tool definition、runtime、transport 與驗證，不負責替你做完整 orchestration。
4. 若需求是「agent 自訂工具專用 server」，先檢查是否已有 `~/.toolanything/agent-mcp/`；有的話整合，沒有才初始化一次。

### Phase 3. 實作

1. 預設顯式寫 `@tool(name=..., description=...)`，不要把公開契約賭在自動推導。
2. class method 跟隨專案既有 decorator 順序；沒有慣例時，優先讓 `@tool(...)` 放外層。
3. 若是 source-based tool，直接用對應 `SourceSpec` 與 `register_*_tool`。
4. 若同一支工具同時要給 MCP / Web / CLI 使用，優先維持同一份 tool module，直接在 `@tool(...)` 補 `cli_command` 或在同一函式加入 CLI 需要的可選參數；不要再額外做一份 `cli_binding.py` 之類的陰影模組。
5. 若要掛到共用自訂工具專用 server，新增或更新 `tools/*.py`，再把載入邏輯掛進共用 `server.py`；不要另開第二個 server entrypoint。

### Phase 4. 驗證

1. 先做安裝驗證與 import 驗證。
2. 再做 registry / `execute_tool` 或 quickstart 層驗證。
3. 若有共用自訂工具專用 server，再驗證 `127.0.0.1:9092/health` 與 `/mcp` 的 `tools/list`。
4. 需要 MCP 連線時，再跑 `doctor`、`serve` 或 `inspect`。

## 必守邊界

1. 不要把「先裝本地 bundle」省略掉，又退回要求使用者看 GitHub repo 安裝。
2. 不要把 OpenClaw、Codex、Claude Code 當成同一種目錄結構。
3. 不要為了包一支新工具去亂改 runtime、transport 或 adapter 核心。
4. 不要重造第二套 schema 或 name mapping，ToolAnything 已處理 MCP 與 OpenAI schema。
5. 若使用者的想法不對，直接指出錯誤並說明原因。

## 交付時要回報什麼

至少交代四件事：

1. 偵測到的 host 與實際安裝路徑。
2. 使用了哪個 wheel，以及 wheel 是從 `wheels/`、`wheel/` 還是 `dist/` 取得。
3. 更新了哪個 `AGENTS.md`，使用了哪種語言。
4. 你選了 `@tool` 還是 source-based API，理由是什麼。
5. 若有共用自訂工具專用 server，server root、port 與自動啟動方式是什麼。
6. 跑了哪些驗證；若沒跑，阻塞點是什麼。

需要平台矩陣、命令清單與驗證細節時，讀：

- `references/local-install.md`
- `references/custom-mcp-server-policy.md`
- `references/workflow.md`
- `references/verification.md`
