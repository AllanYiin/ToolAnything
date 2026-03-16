# Local Install

## 平台判斷矩陣

| Host | 預設偵測條件 | 安裝目標 | 備註 |
| --- | --- | --- | --- |
| Codex | 有 `CODEX_HOME`，或存在 `~/.codex` | `$CODEX_HOME/skills/toolanything-tool-wrapper` 或 `~/.codex/skills/toolanything-tool-wrapper` | 複製整個 skill folder |
| OpenClaw | 存在 `~/.openclaw` 或 `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace/skills/toolanything-tool-wrapper` | 預設不是 `~/.openclaw/skills` |
| Claude Code | 存在 `~/.claude` | `~/.claude/agents/toolanything-tool-wrapper.md` | 由同一份本地內容生成 subagent 檔 |

如果同時符合多個條件，停止並要求顯式 `--host`；不要猜。

## 安裝命令

自動偵測：

```bash
python scripts/install_local_bundle.py --host auto
```

明確指定：

```bash
python scripts/install_local_bundle.py --host codex
python scripts/install_local_bundle.py --host openclaw
python scripts/install_local_bundle.py --host claude-code
```

只想看會做什麼：

```bash
python scripts/install_local_bundle.py --host codex --dry-run
```

## wheel 選擇順序

1. `wheels/toolanything-*.whl`
2. 相容舊路徑 `wheel/toolanything-*.whl`
3. 開發中 fallback：repo `dist/toolanything-*.whl`

若三者都沒有，直接回報 skill bundle 缺件。

## 強制更新規則

安裝腳本必須使用：

```bash
python -m pip install --upgrade --force-reinstall <wheel>
```

理由：

1. 讓目前環境不依賴 PATH 裡是哪一份 `toolanything`。
2. 避免環境已有舊版套件卻沒被刷新。
3. 讓離網或低網依賴流程只依賴本地 wheel。

## 離網限制

這個 bundle 只保證 ToolAnything 本體可以從本地 wheel 重裝，不等於自帶所有依賴的離線 mirror。若環境缺 `fastapi`、`uvicorn`、`opencv-python` 等依賴，應先確保：

1. 這些依賴本來就已存在於目標環境，或
2. 你有額外的本地 wheel mirror / 私有 index 可供安裝

## 成功條件

1. `python -c "import toolanything; print(toolanything.__file__)"` 成功。
2. 本地目標路徑存在最新 skill / subagent。
3. 後續敘事與操作都以這份本地 bundle 為主，而不是把使用者丟回上游 GitHub 安裝文件。
