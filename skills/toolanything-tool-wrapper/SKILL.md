---
name: toolanything-tool-wrapper
description: "適用於使用者仍用舊名稱『ToolAnything tool wrapper』提問時的相容轉接。Treat it as a legacy compatibility alias instead of the default entrypoint: route reusable MCP/OpenAI tool work to `toolanything-mcp-router`, and route local bundle installation, host sync, AGENTS updates, shared custom-server policy, or auto-start work to `toolanything-platform-ops`."
version: 2026.3.17
license: MIT
metadata:
  author: OpenAI Codex
  repo: ToolAnything
---

# ToolAnything Tool Wrapper

This skill name is kept only for backward compatibility.

## What To Do

1. If the user means "should I use ToolAnything for this reusable MCP/OpenAI tool task?", switch to `toolanything-mcp-router`.
2. If the user means "install the local bundle, sync host skills, update AGENTS, or manage the shared custom-tools server", switch to `toolanything-platform-ops`.
3. If both are needed, let the router decide first, then hand off to platform ops.

## What Not To Do

- Do not keep using this legacy name as the default trigger.
- Do not inject the old fallback AGENTS rule.
- Do not make ordinary tool-wrapping work look like platform governance.

## Compatibility Note

The bundled installer is still kept here so older flows continue to work, but its behavior must stay aligned with:

- `toolanything-mcp-router`
- `toolanything-platform-ops`
