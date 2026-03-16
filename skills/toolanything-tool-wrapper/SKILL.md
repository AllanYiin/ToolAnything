---
name: toolanything-tool-wrapper
description: 當使用者要在 Codex、OpenClaw 或 Claude Code 的本地環境中，優先用 skill 內附的 ToolAnything wheel 離網或低網依賴地安裝/更新 ToolAnything，並把 Python function、class method、HTTP API、SQL 或 model source 包成 MCP / OpenAI tool 時使用。適用於偵測 host、同步本地 skill、強制更新 wheel、選擇 @tool 或 source-based API、驗證 tools/list 與 tools/call；不應先把使用者丟回 GitHub repo 自行研究安裝流程。
version: 2026.3.16
license: MIT
metadata:
  author: OpenAI Codex
  repo: ToolAnything
---

# ToolAnything Tool Wrapper

這個 skill 的目標是把 ToolAnything 的使用流程改成「本地 bundle 優先」：先用 skill 內附 wheel 更新本機套件、把 skill 同步到正確平台目錄，再進入 tool wrapper 實作與驗證，而不是先叫使用者去上游 GitHub repo 自行摸索。

## 第一件事一定先做本地安裝

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

這支腳本必須按順序完成三件事：

1. 從 `wheels/` 挑最新的 `toolanything-*.whl`；若缺檔才相容舊的 `wheel/`，最後才回退到 repo `dist/`。
2. 用 `python -m pip install --upgrade --force-reinstall <wheel>` 強制更新本機 ToolAnything。
3. 依 host 把本地 bundle 同步到正確位置：
   - Codex：`$CODEX_HOME/skills/toolanything-tool-wrapper`，若沒有 `CODEX_HOME` 則用 `~/.codex/skills/toolanything-tool-wrapper`
   - OpenClaw：預設 `~/.openclaw/workspace/skills/toolanything-tool-wrapper`
   - Claude Code：產生 `~/.claude/agents/toolanything-tool-wrapper.md`

若腳本找不到 wheel，就停止並回報 skill bundle 打包缺口，不要改成叫使用者去 clone repo 安裝。

## 先糾正幾個容易錯的假設

1. OpenClaw 不是預設裝到 `~/.openclaw/skills/...`；這個 skill 一律以 `~/.openclaw/workspace/skills/...` 為預設，必要時用 `OPENCLAW_WORKSPACE` 覆寫。
2. Claude Code 不是同一種 `SKILL.md` 目錄模型；要落地的是 local subagent 檔，不是直接複製整個 skill folder 當成 Claude skill。
3. 離網只代表 ToolAnything 本體可以從內附 wheel 重裝；若環境缺少 wheel 之外的相依套件，仍要事先準備本地 mirror 或既有依賴。

## 完成本地安裝後，才讀最小必要上下文

先讀 skill 自己的本地說明：

1. `references/local-install.md`
2. `references/workflow.md`
3. `references/verification.md`

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

## 執行流程

### Phase 1. 先做本地 bundle 安裝

1. 先跑 `python scripts/install_local_bundle.py --host auto`。
2. 若偵測到多個 host，改用顯式 `--host`，不要自作主張。
3. 安裝完成後，先確認 `python -c "import toolanything; print(toolanything.__file__)"` 指向剛更新後的環境。

### Phase 2. 判斷工具來源

1. 穩定的 Python callable，優先用 `@tool`。
2. 真正來源若是 HTTP、SQL 或 model artifact，優先用 source-based API。
3. 若使用者把 ToolAnything 誤當成全能 agent framework，直接糾正：這個 repo 主要處理 tool definition、runtime、transport 與驗證，不負責替你做完整 orchestration。

### Phase 3. 實作

1. 預設顯式寫 `@tool(name=..., description=...)`，不要把公開契約賭在自動推導。
2. class method 跟隨專案既有 decorator 順序；沒有慣例時，優先讓 `@tool(...)` 放外層。
3. 若是 source-based tool，直接用對應 `SourceSpec` 與 `register_*_tool`。

### Phase 4. 驗證

1. 先做安裝驗證與 import 驗證。
2. 再做 registry / `execute_tool` 或 quickstart 層驗證。
3. 需要 MCP 連線時，再跑 `doctor`、`serve` 或 `inspect`。

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
3. 你選了 `@tool` 還是 source-based API，理由是什麼。
4. 跑了哪些驗證；若沒跑，阻塞點是什麼。

需要平台矩陣、命令清單與驗證細節時，讀：

- `references/local-install.md`
- `references/workflow.md`
- `references/verification.md`
