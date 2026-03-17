# OPENCLAW

OpenClaw 端的預設入口應是 `toolanything-mcp-router`，不是舊的 fallback skill。

## Routing

- 可重用的 MCP/OpenAI tool、HTTP/SQL/model source、`doctor`/`inspect` 驗證、shared server 需求：先走 `toolanything-mcp-router`
- 本地 bundle 安裝、workspace skill 同步、`AGENTS.md` 注入、shared server / auto-start：交給 `toolanything-platform-ops`
- 只有在 throwaway、MCP-only、單一本地 callable、且完全不需要 `doctor` / `inspect` / CLI / shared server / source-based API 時，才合理改用更小方案

## Skill Metadata

`toolanything-mcp-router` 的 frontmatter 會帶出 OpenClaw discovery 需要的訊號：`skillKey`、`requires.anyBins`、安裝提示與搜尋 tags。請優先維護這份薄 router，而不是把 discovery 訊號埋在重型 ops skill。

## Workspace Notes

- workspace skill 預設路徑是 `~/.openclaw/workspace/skills/`
- `AGENTS.md` 應放在 workspace 層，而不是隨機工作目錄
- 若要用本地 bundle 安裝，可執行 `skills/toolanything-platform-ops/scripts/install_local_bundle.py`
