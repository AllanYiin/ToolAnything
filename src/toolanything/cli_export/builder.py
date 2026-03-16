"""CLI app builder。"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .arg_mapping import add_argument_to_parser, build_argument_specs, parse_tool_arguments
from .config import build_project_config, save_cli_project
from .exceptions import (
    CLIArgumentValidationError,
    CLINamingConflictError,
    CLIOutputSerializationError,
)
from .naming import build_command_definitions
from .runtime_adapter import (
    envelope_exit_code,
    invoke_via_registry,
    render_text_envelope,
    serialize_json_envelope,
    validate_aspect_ratio,
    validate_path_arguments,
)
from .types import (
    CLIAppInspection,
    CLICommandDefinition,
    CLICommandOverride,
    CLIExportOptions,
    CLIProjectConfig,
    EXIT_ARG_VALIDATION_ERROR,
    EXIT_COMMAND_RESOLUTION_ERROR,
    EXIT_INTERRUPTED,
    EXIT_NAMING_CONFLICT_ERROR,
    EXIT_OUTPUT_SERIALIZATION_ERROR,
)
from ..core.models import ToolSpec
from ..core.registry import ToolRegistry


class CLIArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CLIArgumentValidationError(message)


class CLIApp:
    def __init__(
        self,
        registry: ToolRegistry,
        options: CLIExportOptions,
        command_defs: list[CLICommandDefinition],
    ) -> None:
        self.registry = registry
        self.options = options
        self.command_defs = command_defs
        self._parser = self._build_parser()

    def inspect(self) -> CLIAppInspection:
        commands = [
            {
                "tool_name": command.tool_name,
                "command_path": command.command_path,
                "aliases": command.aliases,
                "summary": command.summary,
                "arguments": [asdict(argument) for argument in command.arguments],
            }
            for command in self.command_defs
        ]
        return CLIAppInspection(
            app_name=self.options.app_name,
            description=self.options.app_description,
            commands=commands,
        )

    def _version_string(self) -> str:
        try:
            return version("toolanything")
        except PackageNotFoundError:
            return "0.0.0"

    def _common_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--json", action="store_true", help="輸出 machine-readable JSON")
        parser.add_argument("--output", help="將結果輸出到檔案")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="允許覆寫既有輸出檔案",
        )
        parser.add_argument("--verbose", action="store_true", help="輸出執行細節")
        parser.add_argument("--quiet", action="store_true", help="僅輸出必要結果")
        parser.add_argument(
            "--stream",
            action="store_true",
            help="要求串流輸出（若工具支援）",
        )
        return parser

    def _build_parser(self) -> argparse.ArgumentParser:
        common = self._common_parser()
        parser = CLIArgumentParser(
            prog=self.options.app_name,
            description=self.options.app_description or "ToolAnything CLI export",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            parents=[common],
        )
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {self._version_string()}",
        )
        subparsers = parser.add_subparsers(dest="_command")
        nodes: dict[tuple[str, ...], argparse.ArgumentParser] = {(): parser}
        node_subparsers: dict[tuple[str, ...], Any] = {(): subparsers}

        for command in self.command_defs:
            current_path: list[str] = []
            for segment in command.command_path[:-1]:
                current_path.append(segment)
                key = tuple(current_path)
                if key in nodes:
                    continue
                parent_key = tuple(current_path[:-1])
                parent_parser = nodes[parent_key]
                sp = node_subparsers[parent_key]
                group_parser = sp.add_parser(segment, help=segment, parents=[common])
                nodes[key] = group_parser
                node_subparsers[key] = group_parser.add_subparsers(dest="_".join(key))

            parent_key = tuple(command.command_path[:-1])
            sp = node_subparsers[parent_key]
            leaf = sp.add_parser(
                command.command_path[-1],
                aliases=command.aliases,
                help=command.summary,
                description=command.description,
                parents=[common],
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
            if command.examples:
                leaf.epilog = "Examples:\n" + "\n".join(command.examples)
            for argument in command.arguments:
                add_argument_to_parser(leaf, argument)
            leaf.set_defaults(_cli_command=command)

        return parser

    def _write_output(self, content: str, *, output_path: str | None, overwrite: bool) -> None:
        if not output_path:
            if content:
                print(content)
            return
        path = Path(output_path)
        if path.exists() and not overwrite:
            raise CLIArgumentValidationError(f"輸出檔案已存在: {path}，如要覆寫請加 --overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    async def _run_async(self, argv: list[str]) -> int:
        namespace = self._parser.parse_args(argv)
        command: CLICommandDefinition | None = getattr(namespace, "_cli_command", None)
        if command is None:
            self._parser.print_help()
            return EXIT_COMMAND_RESOLUTION_ERROR

        arguments = parse_tool_arguments(namespace, command.arguments)
        path_fields = {argument.name for argument in command.arguments if argument.path_like}
        validate_path_arguments(arguments, path_fields=path_fields)
        validate_aspect_ratio(arguments, command.metadata)

        output_mode = "json" if namespace.json else self.options.default_output_mode
        envelope = await invoke_via_registry(
            self.registry,
            tool_name=command.tool_name,
            arguments=arguments,
            output_mode=output_mode,
            stream=bool(namespace.stream),
        )

        if output_mode == "json":
            content = serialize_json_envelope(envelope)
        else:
            content = render_text_envelope(envelope)

        if namespace.verbose and envelope.ok:
            meta_block = json.dumps(
                {
                    "tool_name": command.tool_name,
                    "command_path": command.command_path,
                    "output_mode": output_mode,
                },
                ensure_ascii=False,
            )
            content = f"{meta_block}\n{content}"
        if namespace.quiet and envelope.ok:
            content = "" if envelope.result is None else str(envelope.result)

        self._write_output(
            content,
            output_path=namespace.output,
            overwrite=bool(namespace.overwrite),
        )
        return envelope.exit_code

    def run(self, argv: list[str]) -> int:
        try:
            return asyncio.run(self._run_async(argv))
        except KeyboardInterrupt:
            return EXIT_INTERRUPTED
        except CLINamingConflictError:
            return EXIT_NAMING_CONFLICT_ERROR
        except CLIOutputSerializationError:
            return EXIT_OUTPUT_SERIALIZATION_ERROR
        except CLIArgumentValidationError as exc:
            print(f"[ARG_VALIDATION_ERROR] {exc}")
            return EXIT_ARG_VALIDATION_ERROR
        except Exception as exc:
            code = envelope_exit_code(exc)
            print(f"[CLI_ERROR] {exc}")
            return code


def _filter_tools(registry: ToolRegistry, options: CLIExportOptions) -> list[ToolSpec]:
    specs = registry.list()
    if options.include_tools:
        include = set(options.include_tools)
        specs = [spec for spec in specs if spec.name in include]
    if options.exclude_tools:
        exclude = set(options.exclude_tools)
        specs = [spec for spec in specs if spec.name not in exclude]
    return specs


def build_cli_app(
    registry: ToolRegistry,
    options: CLIExportOptions,
    project_config: CLIProjectConfig | None = None,
) -> CLIApp:
    tools = _filter_tools(registry, options)
    overrides = project_config.command_overrides if project_config else None
    command_defs = build_command_definitions(tools, options=options, overrides=overrides)
    tool_index = {tool.name: tool for tool in tools}
    for command in command_defs:
        command.arguments = build_argument_specs(tool_index[command.tool_name])
    return CLIApp(registry, options, command_defs)


def export_cli_project(
    registry: ToolRegistry,
    config_path: str,
    options: CLIExportOptions,
    *,
    module: str | None = None,
    launcher_path: str | None = None,
    command_overrides: dict[str, CLICommandOverride] | None = None,
) -> CLIProjectConfig:
    tools = _filter_tools(registry, options)
    config = build_project_config(
        options=options,
        tools=[tool.name for tool in tools],
        module=module,
        launcher_path=launcher_path,
    )
    if command_overrides:
        config.command_overrides = command_overrides
    save_cli_project(config, config_path)
    return config


def write_cli_launcher(config_path: str, launcher_path: str) -> None:
    target = Path(launcher_path)
    if target.exists():
        raise CLIArgumentValidationError(f"launcher 已存在: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "from __future__ import annotations\n"
        "import sys\n"
        "from toolanything.cli import run_exported_cli\n\n"
        f"if __name__ == '__main__':\n"
        f"    raise SystemExit(run_exported_cli(config_path={config_path!r}, argv=sys.argv[1:]))\n"
    )
    target.write_text(content, encoding="utf-8")
