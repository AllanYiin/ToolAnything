"""Registration metadata helpers for standard tools."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from toolanything.core import ToolRegistry, ToolSpec


def register_callable(
    registry: ToolRegistry,
    func: Any,
    *,
    name: str,
    description: str,
    category: str,
    scopes: tuple[str, ...],
    read_only: bool,
    open_world: bool,
    destructive: bool = False,
    requires_approval: bool = False,
    cli_arguments: Mapping[str, Mapping[str, Any]] | None = None,
    output_schema: Mapping[str, Any] | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> ToolSpec:
    """Create and register a standard ToolSpec with shared adapter metadata."""

    metadata = {
        "toolanything_stdlib": True,
        "title": name,
        "category": category,
        "scopes": list(scopes),
        "side_effect": not read_only,
        "risk_level": "medium" if not read_only else "low",
        "requires_approval": requires_approval,
        "cli": {
            "command_path": cli_command_path(name),
            "summary": description,
            "arguments": {
                "root_id": {"path_like": False},
                "relative_path": {"path_like": False},
            },
        },
        "mcp_annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": read_only,
            "openWorldHint": open_world,
        },
    }
    metadata["output_schema"] = (
        dict(output_schema)
        if output_schema
        else {"type": "object", "additionalProperties": True}
    )
    if cli_arguments:
        metadata["cli"]["arguments"].update(  # type: ignore[index, union-attr]
            {name: dict(value) for name, value in cli_arguments.items()}
        )
    if extra_metadata:
        metadata = merge_metadata(metadata, extra_metadata)
    spec = ToolSpec.from_function(
        func,
        name=name,
        description=description,
        adapters=("openai", "mcp"),
        tags=("standard", category),
        metadata=metadata,
    )
    registry.register(spec)
    return spec


def cli_command_path(tool_name: str) -> list[str]:
    parts = [part for part in tool_name.split(".") if part]
    return [part.replace("_", "-") for part in parts] or ["standard", "tool"]


def positive_limit(value: int, *, default: int) -> int:
    if value <= 0:
        return default
    return value


def merge_metadata(
    base: dict[str, Any],
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if key == "cli" and isinstance(value, Mapping) and isinstance(merged.get("cli"), dict):
            cli = dict(merged["cli"])
            for cli_key, cli_value in value.items():
                if cli_key == "arguments" and isinstance(cli_value, Mapping) and isinstance(cli.get("arguments"), dict):
                    arguments = dict(cli["arguments"])
                    arguments.update({str(name): dict(arg) for name, arg in cli_value.items() if isinstance(arg, Mapping)})
                    cli["arguments"] = arguments
                else:
                    cli[cli_key] = cli_value
            merged["cli"] = cli
        else:
            merged[key] = value
    return merged
