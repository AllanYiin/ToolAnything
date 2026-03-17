# Workflow

## Router Then Ops

1. Let `toolanything-mcp-router` decide whether ToolAnything should be the default path.
2. Only when the task crosses into bundle install, host rollout, AGENTS sync, shared-server policy, or auto-start should `toolanything-platform-ops` take over.

This split exists to avoid making simple tool-wrapping requests look like platform governance work.

## Implementation Matrix

| Situation | Preferred path | Avoid | Evidence |
| --- | --- | --- | --- |
| Stable Python function | `@tool(...)` | adding a thin extra adapter | `examples/quickstart/01_define_tools.py` |
| Class method | `@tool(...)` with project-consistent decorator order | rewriting descriptor mechanics by hand | `examples/class_method_tools/README.md` |
| HTTP source | source-based HTTP APIs | a wrapper that only forwards the request | `examples/non_function_tools/http_tool.py` |
| SQL source | source-based SQL APIs | hiding SQL inside a fake callable-first story | `examples/non_function_tools/sql_tool.py` |
| Model source | source-based model APIs | extra service glue with no contract value | `examples/non_function_tools/` |
| Reusable host tool | integrate into `~/.toolanything/agent-mcp/` | one long-lived server per tool | `references/custom-mcp-server-policy.md` |

## Canonical Shared Server Flow

1. Check whether `~/.toolanything/agent-mcp/` already exists.
2. If it exists, add the tool under `tools/` and load it from the shared `server.py`.
3. If it does not exist, initialize it once, keep `127.0.0.1:9092`, and document the auto-start method.
4. Verify `/health`, `/mcp` `tools/list`, and the new tool call.

## When To Correct The User

Correct the user immediately when they:

1. treat ToolAnything as fallback even though the task is reusable, dual-protocol, or source-based
2. ask for a second long-lived server without a real security/runtime/deployment boundary
3. want to hand-maintain another MCP/OpenAI schema layer
4. point OpenClaw or Claude Code at the wrong local path
