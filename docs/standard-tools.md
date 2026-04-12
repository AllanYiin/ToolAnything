# Standard Tools

This document is a reference for the reusable ToolAnything standard tool bundle.
It targets agent-platform builders who want common capabilities without creating a
new wrapper for every project.

## Scope

The bundle is opt-in. Calling `register_standard_tools()` registers tools into
the registry you pass in. It does not change the global tool set unless you pass
no registry and intentionally use the global registry.

Implementation modules are split by responsibility:

- `toolanything.standard_tools.web`: network-facing read-only tools and SSRF checks.
- `toolanything.standard_tools.filesystem`: root-scoped filesystem tools and write guards.
- `toolanything.standard_tools.data`: dependency-free data transformation helpers.
- `toolanything.standard_tools.registration`: shared MCP/OpenAI/CLI metadata projection.
- `toolanything.standard_tools.tools`: backward-compatible bundle facade.

Included by default:

- `standard.web.*`: read-only HTTP(S) fetch, text extraction, link extraction,
  and provider-backed search.
- `standard.fs.*`: root-scoped list, stat, text read, and search.
- `standard.data.*`: JSON parsing, small JSON Schema subset validation, CSV
  inspection, and Markdown link extraction.

Not included:

- Memory, session, todo, delegation, cron, process, shell, code execution, and
  browser-control tools.
- Destructive filesystem operations such as delete, move, or recursive overwrite.

## Quick Start

```python
from pathlib import Path

from toolanything import (
    StandardToolOptions,
    ToolRegistry,
    register_standard_tools,
)

registry = ToolRegistry()
register_standard_tools(
    registry,
    StandardToolOptions(roots={"workspace": Path.cwd()}),
)

mcp_tools = registry.to_mcp_tools()
openai_tools = registry.to_openai_tools()
tool_manifest = registry.to_tool_manifest(tags=["standard"])
```

The same registry can also be exported as a CLI app:

```python
from toolanything import CLIExportOptions, build_cli_app

app = build_cli_app(registry, CLIExportOptions(app_name="stdtools"))
app.run(["standard", "data", "json-parse", "--text", '{"ok": true}', "--json"])
```

Write tools are disabled by default. Enable them only for roots that should be
writable:

```python
from toolanything import StandardToolOptions, StandardToolRoot

register_standard_tools(
    registry,
    StandardToolOptions(
        roots=(StandardToolRoot("workspace", Path.cwd(), writable=True),),
        include_write_tools=True,
    ),
)
```

## Safety Model

Filesystem tools use named roots. Tool calls should pass `root_id` and a
relative path. Absolute paths and `..` traversal that escapes the configured
root are rejected.

Web tools reject non-HTTP(S) URLs and validate redirects. By default they block
private, loopback, link-local, reserved, multicast, carrier-grade NAT, and cloud
metadata addresses to reduce SSRF risk. For local development tests, set
`allow_private_network=True`.

Write tools are opt-in and guarded:

- `standard.fs.write_create_only` fails if the target already exists.
- `standard.fs.replace_if_match` requires the current file SHA-256.
- `standard.fs.patch_text` previews by default; applying requires the current
  file SHA-256.

MCP annotations are exported when present in tool metadata. They are hints for
hosts and clients, not a replacement for runtime policy enforcement.

## CLI Commands

Standard tools define stable CLI command paths through `metadata["cli"]`.
Command paths keep the tool namespace:

- `standard.web.fetch` -> `standard web fetch`
- `standard.web.extract_text` -> `standard web extract-text`
- `standard.fs.read_text` -> `standard fs read-text`
- `standard.fs.patch_text` -> `standard fs patch-text`
- `standard.data.json_parse` -> `standard data json-parse`

The CLI layer still invokes the same registered `ToolSpec`, so MCP, OpenAI tool
calling, and CLI share one schema and one execution path.

Filesystem tools also set CLI argument metadata so `relative_path` is treated as
a sandbox-relative value, not as a path that must exist in the current shell
working directory.

Example:

```bash
stdtools standard fs read-text --root-id workspace --relative-path README.md --json
```

Guarded write example:

```bash
stdtools standard fs patch-text \
  --root-id workspace \
  --relative-path draft.txt \
  --old-string before \
  --new-string after \
  --expected-sha256 "<current-sha256>" \
  --no-dry-run \
  --json
```

Single-file unified diff patches are also supported:

```bash
stdtools standard fs apply-unified-patch \
  --root-id workspace \
  --relative-path draft.txt \
  --patch "<unified-diff-text>" \
  --expected-sha256 "<current-sha256>" \
  --no-dry-run \
  --json
```

`standard.fs.apply_unified_patch` intentionally supports one target file per
call. It validates hunk context against the current file and requires
`expected_sha256` when applying.

## Search Provider

`standard.web.search` is registered as part of the web bundle, but it requires a
caller-supplied provider. The provider receives `(query, limit)` and should
return either a list or `{"results": list}`.

```python
def search_provider(query: str, limit: int):
    return [{"title": "Example", "url": "https://example.com", "snippet": query}][:limit]

register_standard_tools(
    registry,
    StandardToolOptions(search_provider=search_provider),
)
```

## Optional Enhancements

The standard tools avoid mandatory heavy dependencies, but use stronger engines
when they are available:

- `standard.data.json_validate` uses the optional `jsonschema` package when it
  is installed. Otherwise it falls back to a small built-in subset validator.
- `standard.fs.search` uses `rg --json` for content search when ripgrep is on
  `PATH`. If ripgrep is missing or fails, it falls back to the stdlib scanner.
- `standard.web.extract_text` filters common non-content HTML blocks such as
  `script`, `style`, `nav`, `header`, and `footer` before returning text.

`ToolRegistry.to_tool_manifest(tags=["standard"])` exports the canonical
ToolAnything manifest. Use it for host UIs, policy engines, or agent runtimes
that need full metadata beyond what MCP or OpenAI tool schemas can carry.

## Configuration

Important `StandardToolOptions` fields:

- `roots`: mapping or sequence of `StandardToolRoot`.
- `include_write_tools`: enables guarded write tools.
- `allowed_domains` / `blocked_domains`: web domain policy.
- `allow_private_network`: allows private network fetches for local dev.
- `max_file_bytes`, `max_read_chars`, `max_search_results`, `max_web_bytes`:
  resource limits.
- `web_timeout_sec`, `web_user_agent`: HTTP runtime settings.
- `search_provider`: implementation for `standard.web.search`.

## Verification

Run the focused test file:

```bash
pytest tests/test_standard_tools.py
```
