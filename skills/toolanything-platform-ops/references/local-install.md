# Local Install

## Skills Deployed Together

`install_local_bundle.py` must deploy these entries as one bundle:

- `toolanything-mcp-router`
- `toolanything-platform-ops`
- `toolanything-tool-wrapper` (legacy alias)

The goal is to keep the thin router discoverable while still shipping the heavy operational workflow and the old compatibility name.

## Host Matrix

| Host | Detect by default | Skill targets | AGENTS target | Notes |
| --- | --- | --- | --- | --- |
| Codex | `CODEX_HOME` or `~/.codex` exists | `$CODEX_HOME/skills/<skill>` or `~/.codex/skills/<skill>` | `$CODEX_HOME/AGENTS.md` or `~/.codex/AGENTS.md` | Copy the three skill folders |
| OpenClaw | `OPENCLAW_WORKSPACE` or `~/.openclaw` exists | `$OPENCLAW_WORKSPACE/skills/<skill>` or `~/.openclaw/workspace/skills/<skill>` | `$OPENCLAW_WORKSPACE/AGENTS.md` or `~/.openclaw/workspace/AGENTS.md` | Default is not `~/.openclaw/skills` |
| Claude Code | `~/.claude` exists | `~/.claude/skills/<skill>.md` | `~/.claude/AGENTS.md` | Generate one local Markdown skill file per entry |

If more than one host matches, stop and require `--host`.

## AGENTS Rule

The installer must inject the new router-first decision rule, not the old fallback rule.

繁中：

```text
當任務涉及建立、包裝、擴充或驗證可重用的 MCP/OpenAI tool，或工具來源是 Python function、class method、HTTP API、SQL、model inference 時，先載入 skill: ToolAnything MCP router（toolanything-mcp-router）。
只有在以下條件同時成立時，才可優先改用 FastMCP 或其他更小方案：
1. 需求是一次性原型；
2. 只需要 MCP，不需要 OpenAI tool calling；
3. 來源是單一本地 Python callable；
4. 不需要 doctor / inspect / CLI / shared server / source-based API。
若任務進入本地 bundle 安裝、shared server、host 同步或自動啟動，改載入 skill: ToolAnything platform ops（toolanything-platform-ops）。
```

英文：

```text
When a task involves creating, wrapping, extending, or validating reusable MCP/OpenAI tools, or when the tool source is a Python function, class method, HTTP API, SQL query, or model inference, load the skill: ToolAnything MCP router (toolanything-mcp-router) first.
FastMCP or another smaller solution is acceptable only when all of the following are true:
1. the result is a throwaway prototype;
2. MCP-only is needed;
3. the source is a single local Python callable;
4. no doctor / inspect / CLI / shared server / source-based API is needed.
If the task moves into local bundle installation, shared server setup, host sync, or auto-start, load the skill: ToolAnything platform ops (toolanything-platform-ops).
```

The installer must replace any legacy `toolanything-tool-wrapper` block instead of appending a second, contradictory rule.

## Wheel Selection Order

1. `wheels/toolanything-*.whl`
2. legacy `wheel/toolanything-*.whl`
3. repo `dist/toolanything-*.whl`

If none exist, stop and report the missing artifact.

## Force-Reinstall Rule

Always install with:

```bash
python -m pip install --upgrade --force-reinstall <wheel>
```

Reason:

1. it refreshes the currently active Python environment instead of trusting PATH
2. it avoids stale ToolAnything installs
3. it keeps low-network or offline flows centered on the bundled wheel

## Success Criteria

1. `python -c "import toolanything; print(toolanything.__file__)"` succeeds.
2. The deployed host contains the router, ops skill, and legacy alias.
3. `AGENTS.md` contains the new decision rule exactly once.
4. The old fallback wording is removed if it existed before.
