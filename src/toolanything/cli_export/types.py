"""CLI export 型別與常數。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


CLIProjectState = Literal["draft", "configured", "generated", "validated", "archived"]
CLIOutputMode = Literal["text", "json", "stream"]
CLICommandNaming = Literal["flat", "grouped"]


EXIT_SUCCESS = 0
EXIT_ARG_VALIDATION_ERROR = 2
EXIT_COMMAND_RESOLUTION_ERROR = 3
EXIT_RUNTIME_INVOCATION_ERROR = 4
EXIT_TOOL_EXECUTION_ERROR = 5
EXIT_OUTPUT_SERIALIZATION_ERROR = 6
EXIT_PROJECT_CONFIG_ERROR = 7
EXIT_NAMING_CONFLICT_ERROR = 8
EXIT_UNSUPPORTED_FEATURE = 9
EXIT_INTERRUPTED = 130


@dataclass
class CLIExportOptions:
    app_name: str
    app_description: str | None = None
    command_naming: CLICommandNaming = "grouped"
    default_output_mode: Literal["text", "json"] = "text"
    enable_streaming: bool = True
    include_tools: list[str] | None = None
    exclude_tools: list[str] | None = None
    aliases: dict[str, str] = field(default_factory=dict)
    overwrite: bool = False


@dataclass
class CLICommandOverride:
    command_path: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    hidden: bool = False
    summary: str | None = None
    examples: list[str] = field(default_factory=list)


@dataclass
class CLIProjectConfig:
    version: str
    app_name: str
    tools: list[str]
    command_overrides: dict[str, CLICommandOverride] = field(default_factory=dict)
    default_output_mode: str = "text"
    generated_at: str | None = None
    state: CLIProjectState = "draft"
    app_description: str | None = None
    module: str | None = None
    launcher_path: str | None = None


@dataclass(frozen=True)
class CLIArgumentSpec:
    name: str
    option_strings: tuple[str, ...]
    schema: dict[str, Any]
    required: bool
    help_text: str | None = None
    kind: str = "scalar"
    path_like: bool = False

    @property
    def dest(self) -> str:
        return self.name.replace("-", "_")


@dataclass
class CLICommandDefinition:
    tool_name: str
    command_path: list[str]
    aliases: list[str] = field(default_factory=list)
    summary: str | None = None
    description: str | None = None
    examples: list[str] = field(default_factory=list)
    hidden: bool = False
    source_type: str = "callable"
    metadata: dict[str, Any] = field(default_factory=dict)
    arguments: list[CLIArgumentSpec] = field(default_factory=list)


@dataclass
class CLIInvocationEnvelope:
    ok: bool
    tool_name: str
    exit_code: int
    output_mode: CLIOutputMode
    result: Any | None = None
    error: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class CLIAppInspection:
    app_name: str
    description: str | None
    commands: list[dict[str, Any]]
