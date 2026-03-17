"""Tool name -> CLI command path 命名規則。"""
from __future__ import annotations

import re
from collections import defaultdict

from .exceptions import CLINamingConflictError
from .types import CLICommandDefinition, CLICommandOverride, CLIExportOptions
from ..core.models import ToolSpec


_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")


def normalize_cli_segment(segment: str) -> str:
    slug = _NON_ALNUM_RE.sub("-", segment.strip()).strip("-").lower()
    return slug or "tool"


def tool_name_to_command_path(tool_name: str, command_naming: str = "grouped") -> list[str]:
    if command_naming == "flat":
        return [normalize_cli_segment(tool_name)]
    segments = [normalize_cli_segment(part) for part in tool_name.split(".") if part]
    return segments or ["tool"]


def _command_path_from_cli_metadata(cli_metadata: dict[str, object]) -> list[str]:
    raw_command_path = cli_metadata.get("command_path")
    if isinstance(raw_command_path, list):
        return [
            normalize_cli_segment(str(part))
            for part in raw_command_path
            if str(part).strip()
        ]

    raw_command = cli_metadata.get("command")
    if isinstance(raw_command, str):
        return [
            normalize_cli_segment(segment)
            for segment in raw_command.split()
            if segment.strip()
        ]
    return []


def _metadata_override(tool: ToolSpec) -> CLICommandOverride | None:
    raw_cli = tool.metadata.get("cli")
    if not isinstance(raw_cli, dict):
        return None

    command_path = _command_path_from_cli_metadata(raw_cli)
    aliases_value = raw_cli.get("aliases")
    aliases = (
        [str(alias) for alias in aliases_value if str(alias).strip()]
        if isinstance(aliases_value, list)
        else []
    )
    examples_value = raw_cli.get("examples")
    examples = (
        [str(example) for example in examples_value if str(example).strip()]
        if isinstance(examples_value, list)
        else []
    )
    summary = raw_cli.get("summary")
    hidden = bool(raw_cli.get("hidden", False))

    if not any((command_path, aliases, examples, summary, hidden)):
        return None

    return CLICommandOverride(
        command_path=command_path,
        aliases=aliases,
        hidden=hidden,
        summary=str(summary) if summary is not None else None,
        examples=examples,
    )


def _override_aliases(
    tool_name: str,
    override: CLICommandOverride | None,
    options: CLIExportOptions,
) -> list[str]:
    aliases: list[str] = []
    if override:
        aliases.extend(normalize_cli_segment(alias) for alias in override.aliases if alias)
    raw_alias = options.aliases.get(tool_name)
    if raw_alias:
        aliases.extend(
            normalize_cli_segment(part)
            for part in raw_alias.split(",")
            if part.strip()
        )
    deduped: list[str] = []
    for alias in aliases:
        if alias and alias not in deduped:
            deduped.append(alias)
    return deduped


def build_command_definitions(
    tools: list[ToolSpec],
    *,
    options: CLIExportOptions,
    overrides: dict[str, CLICommandOverride] | None = None,
) -> list[CLICommandDefinition]:
    overrides = overrides or {}
    definitions: list[CLICommandDefinition] = []
    seen_paths: dict[tuple[str, ...], str] = {}
    alias_paths: defaultdict[tuple[str, ...], list[str]] = defaultdict(list)

    for tool in tools:
        override = overrides.get(tool.name) or _metadata_override(tool)
        command_path = (
            [normalize_cli_segment(part) for part in override.command_path]
            if override and override.command_path
            else tool_name_to_command_path(tool.name, options.command_naming)
        )
        path_key = tuple(command_path)
        if path_key in seen_paths:
            raise CLINamingConflictError(
                f"CLI 命名衝突: {' '.join(command_path)} 同時對應 {seen_paths[path_key]} 與 {tool.name}"
            )

        aliases = _override_aliases(tool.name, override, options)
        definitions.append(
            CLICommandDefinition(
                tool_name=tool.name,
                command_path=command_path,
                aliases=aliases,
                summary=(override.summary if override and override.summary else tool.description),
                description=tool.description,
                examples=list(override.examples if override else []),
                hidden=bool(override.hidden) if override else False,
                source_type=tool.source_type,
                metadata=dict(tool.metadata),
            )
        )
        seen_paths[path_key] = tool.name
        for alias in aliases:
            alias_path = tuple(command_path[:-1] + [alias])
            alias_paths[alias_path].append(tool.name)

    conflicts = {
        path: names
        for path, names in alias_paths.items()
        if len(names) > 1 or path in seen_paths
    }
    if conflicts:
        path, names = next(iter(conflicts.items()))
        joined = ", ".join(names)
        raise CLINamingConflictError(
            f"CLI alias 衝突: {' '.join(path)} 對應 {joined}"
        )

    return sorted(definitions, key=lambda item: item.command_path)
