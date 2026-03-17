# CLAUDE

Claude 相關整合分成兩條線：

1. ToolAnything runtime / MCP server 整合
2. Claude 本地 skill 文件的 router / ops 分工

## Runtime Integration

如果你要把 ToolAnything server 接到 Claude Desktop 或 Claude Code，先看：

- `toolanything install-claude --module <module> --port <port>`
- `toolanything init-claude --module <module> --port <port>`

`stdio` 適合 Desktop host 的直接連線；shared custom-tools server 預設仍以 `streamable-http` + `127.0.0.1:9092` 為主。

## Local Skill Split

- `toolanything-mcp-router`：先做選型與 quick path
- `toolanything-platform-ops`：處理 bundle install、shared server、host sync、AGENTS
- `toolanything-tool-wrapper`：只保留給舊名稱相容

本 repo 的本地 installer 會把 Claude 端 skill 寫成 `~/.claude/skills/*.md`，並更新 `~/.claude/AGENTS.md`。
