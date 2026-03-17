---
name: toolanything-platform-ops
description: "適用於使用者要求安裝內附 ToolAnything wheel、同步 Codex/OpenClaw/Claude 本地 skills、更新 AGENTS 規則、管理 shared custom-tool server、固定 port 或設定 auto-start，且 `toolanything-mcp-router` 已先判定應採用 ToolAnything。It is the heavy operational skill for bundled installs, canonical server governance, and host rollout; it is not the first routing entrypoint for simple tool wrapping."
version: 2026.3.17
license: MIT
metadata:
  author: OpenAI Codex
  repo: ToolAnything
---

# ToolAnything Platform Ops

This is the heavy operational skill. Do not load it first for ordinary "wrap a function as a tool" work. `toolanything-mcp-router` should own the initial routing decision, then hand off here only when the task needs bundle installation, host rollout, AGENTS synchronization, shared-server policy, or auto-start.

## Primary Responsibilities

- install or refresh ToolAnything from the bundled local wheel
- sync the local skills or Claude subagents for Codex, OpenClaw, and Claude Code
- inject the ToolAnything decision rule into the correct `AGENTS.md`
- keep reusable custom tools inside one canonical shared server
- enforce fixed host and port policy, plus platform-specific auto-start

## First Action

Run the bundled installer from this skill folder:

```bash
python scripts/install_local_bundle.py --host auto
```

If multiple hosts are detected, stop and rerun with an explicit host:

```bash
python scripts/install_local_bundle.py --host codex
python scripts/install_local_bundle.py --host openclaw
python scripts/install_local_bundle.py --host claude-code
```

The installer must:

1. pick the newest `toolanything-*.whl` from `wheels/`, then legacy `wheel/`, then repo `dist/`
2. force-reinstall the local ToolAnything package from that wheel
3. sync the bundle skills to the correct host-specific locations
4. replace any legacy fallback AGENTS rule with the new router-first decision rule

If the wheel is missing, stop and report a bundle packaging gap. Do not send the user back to GitHub install docs.

## Bundle Layout

This operational bundle deploys three skill entrypoints together:

- `toolanything-mcp-router`: thin router and quick path
- `toolanything-platform-ops`: heavy host and server operations
- `toolanything-tool-wrapper`: legacy compatibility alias

## Host Targets

### Codex

- skills path: `$CODEX_HOME/skills/` or `~/.codex/skills/`
- agents file: `$CODEX_HOME/AGENTS.md` or `~/.codex/AGENTS.md`

### OpenClaw

- skills path: `$OPENCLAW_WORKSPACE/skills/` or `~/.openclaw/workspace/skills/`
- agents file: `$OPENCLAW_WORKSPACE/AGENTS.md` or `~/.openclaw/workspace/AGENTS.md`

### Claude Code

- local skill path: `~/.claude/skills/*.md`
- agents file: `~/.claude/AGENTS.md`

Do not collapse these hosts into one directory model. If the user suggests the wrong path, correct them directly and continue with the correct target.

## Shared Custom Tool Server Policy

When the task is to add a reusable custom tool for an agent host, do not create one long-lived MCP server per tool.

Use one canonical server root per machine:

- Windows: `%USERPROFILE%\\.toolanything\\agent-mcp\\`
- macOS / Linux: `~/.toolanything/agent-mcp/`

Expected structure:

- `server.py`
- `tools/`
- `toolanything-server.json`

Default runtime policy:

- host: `127.0.0.1`
- port: `9092`
- transport: `streamable-http`

Only allow a second shared server when there is a clearly different security boundary, Python runtime, or deployment owner.

## Workflow

### Phase 1. Install and sync

1. Run the local bundle installer.
2. Confirm the installed ToolAnything import path:

```bash
python -c "import toolanything; print(toolanything.__file__)"
```

3. Confirm the correct skills or Claude subagents were written to the host-specific location.
4. Confirm the updated `AGENTS.md` contains the new router-first decision rule and no duplicate legacy block.

### Phase 2. Decide the implementation path

1. Stable Python callable: prefer `@tool(...)`.
2. HTTP, SQL, or model source: prefer the source-based APIs.
3. Shared custom tool server need: integrate into the canonical server instead of creating another long-lived server.

### Phase 3. Implement without spreading policy drift

1. Keep tool contracts explicit with `name` and `description`.
2. Reuse one tool module across MCP, OpenAI, and CLI where possible.
3. If you add a tool to the shared server, place it under `tools/` and load it from the shared `server.py`.
4. Do not invent a second schema layer or a second long-lived server just to get one tool running.

### Phase 4. Verify

Run the cheapest useful checks first:

```bash
toolanything doctor --mode http --url http://127.0.0.1:9092
toolanything inspect
```

Also verify:

- `http://127.0.0.1:9092/health`
- `/mcp` can answer `tools/list`
- the new tool is callable and lives inside the shared server

## Boundaries

- This skill does not decide whether ToolAnything or FastMCP should win first. That belongs to `toolanything-mcp-router`.
- This skill does not replace product architecture or orchestration decisions.
- This skill should not expand into unrelated repo refactors outside the tool layer or shared-server policy.

## Delivery Checklist

Always report:

1. detected host and actual install path
2. selected wheel and its source folder
3. which `AGENTS.md` was updated and whether a legacy block was replaced
4. whether you chose `@tool(...)` or a source-based API, plus why
5. whether a shared custom tool server was touched, including root and port
6. which validations ran, or what blocked them
