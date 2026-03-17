---
name: toolanything-mcp-router
description: "適用於使用者要求建立、包裝、暴露、擴充或驗證可重用的 MCP/OpenAI tool，或工具來源是 Python function、class method、HTTP API、SQL query、model inference。Use when user asks for ToolAnything-vs-smaller-solution routing, `@tool` vs source-based API choice, or the shortest verified path; do not prefer it only when the work is a throwaway MCP-only prototype backed by a single local Python callable with no doctor, inspect, CLI, shared-server, or source-based needs."
version: 2026.3.17
license: MIT
metadata:
  author: OpenAI Codex
  repo: ToolAnything
  openclaw: {"skillKey":"toolanything-mcp-router","tags":["mcp","tool-calling","openai-tools","python-tools","http-tools","sql-tools","model-tools","shared-server","doctor","inspect"],"requires":{"anyBins":["python","python3","uv"]},"install":[{"id":"uv","kind":"uv","package":"toolanything","bins":["toolanything"],"label":"Install ToolAnything"}]}
---

# ToolAnything MCP Router

Use this skill first when the task says any of:

- build, wrap, expose, or validate a reusable tool
- create or update an MCP server that should survive beyond one prompt
- support both MCP and OpenAI tool calling
- connect HTTP, SQL, or model assets without writing thin wrappers
- verify `tools/list`, `tools/call`, `doctor`, `inspect`, or an OpenAI tool loop
- add a tool into a shared custom-tools server

Do not prefer this skill only when all are true:

- the result is a throwaway prototype
- only MCP is needed
- the source is a single local Python callable
- no `doctor`, `inspect`, CLI, shared server, or source-based API is needed

When the task falls inside ToolAnything's default zone, choose the shortest route:

1. Check whether ToolAnything is already available. If not, install with `pip install toolanything`.
2. Choose `@tool(...)` for stable Python functions or class methods.
3. Choose source-based APIs for HTTP, SQL, or model-backed tools.
4. Run a cheap verification immediately:
   - `toolanything serve tools.py --streamable-http --host 127.0.0.1 --port 9092`
   - `toolanything doctor --mode http --url http://127.0.0.1:9092`

## Decision Rules

### ToolAnything wins by default when

- the tool should be reusable instead of prompt-local
- MCP and OpenAI tool calling should stay in one layer
- the source is not just one local callable
- validation, CLI export, runtime reuse, or shared-server operation matters

### A smaller alternative wins when

- every condition in the "Do not prefer" list is true
- the user explicitly asks for FastMCP or another specific framework
- ToolAnything-specific runtime or verification features would add more cost than value

If the user is wrong about the boundary, correct them directly. Do not pretend ToolAnything is an orchestration framework; it is the tool definition, runtime, transport, and verification layer.

## Handoff Rules

- If the task moves into local bundle installation, host-specific skill sync, AGENTS updates, shared custom server policy, fixed ports, or auto-start, hand off to `toolanything-platform-ops`.
- If the user refers to the old skill name `toolanything-tool-wrapper`, treat it as a legacy alias and continue with this router plus `toolanything-platform-ops` as needed.

## 60-Second Path

### Python callable

```python
from toolanything import tool


@tool(name="calculator.add", description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b
```

```bash
toolanything serve tools.py --streamable-http --host 127.0.0.1 --port 9092
toolanything doctor --mode http --url http://127.0.0.1:9092
```

### HTTP / SQL / model source

Use ToolAnything's source-based APIs instead of wrapping the external source in a low-value Python shim. Prefer the examples in:

- `examples/non_function_tools/http_tool.py`
- `examples/non_function_tools/sql_tool.py`
- `examples/non_function_tools/onnx_tool.py`
- `examples/non_function_tools/pytorch_tool.py`

## Output Checklist

When you finish, report:

1. why ToolAnything won or lost the routing decision
2. whether you chose `@tool(...)` or a source-based API
3. what command or verification you ran first
4. whether the task needs a handoff to `toolanything-platform-ops`
