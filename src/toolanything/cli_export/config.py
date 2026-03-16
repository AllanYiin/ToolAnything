"""CLI project config 讀寫。"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .exceptions import CLIProjectConfigError
from .types import CLICommandOverride, CLIExportOptions, CLIProjectConfig


CURRENT_CONFIG_VERSION = "1"
DEFAULT_CONFIG_FILENAME = "toolanything.cli.json"


def _override_from_dict(payload: dict) -> CLICommandOverride:
    return CLICommandOverride(
        command_path=list(payload.get("command_path") or []),
        aliases=list(payload.get("aliases") or []),
        hidden=bool(payload.get("hidden", False)),
        summary=payload.get("summary"),
        examples=list(payload.get("examples") or []),
    )


def cli_project_to_dict(config: CLIProjectConfig) -> dict:
    payload = asdict(config)
    payload["command_overrides"] = {
        name: asdict(override) for name, override in config.command_overrides.items()
    }
    return payload


def cli_project_from_dict(payload: dict) -> CLIProjectConfig:
    if not isinstance(payload, dict):
        raise CLIProjectConfigError("CLI project config 必須是 object")

    try:
        overrides_payload = payload.get("command_overrides") or {}
        overrides = {
            name: _override_from_dict(value)
            for name, value in overrides_payload.items()
        }
        return CLIProjectConfig(
            version=str(payload.get("version") or CURRENT_CONFIG_VERSION),
            app_name=str(payload["app_name"]),
            tools=list(payload.get("tools") or []),
            command_overrides=overrides,
            default_output_mode=str(payload.get("default_output_mode") or "text"),
            generated_at=payload.get("generated_at"),
            state=str(payload.get("state") or "draft"),
            app_description=payload.get("app_description"),
            module=payload.get("module"),
            launcher_path=payload.get("launcher_path"),
        )
    except KeyError as exc:
        raise CLIProjectConfigError(f"CLI project config 缺少欄位: {exc.args[0]}") from exc


def load_cli_project(config_path: str) -> CLIProjectConfig:
    path = Path(config_path)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CLIProjectConfigError(f"找不到 CLI project config: {path}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CLIProjectConfigError(
            f"CLI project config JSON 解析失敗: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    return cli_project_from_dict(payload)


def save_cli_project(config: CLIProjectConfig, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(cli_project_to_dict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_project_config(
    *,
    options: CLIExportOptions,
    tools: list[str],
    module: str | None = None,
    launcher_path: str | None = None,
) -> CLIProjectConfig:
    return CLIProjectConfig(
        version=CURRENT_CONFIG_VERSION,
        app_name=options.app_name,
        app_description=options.app_description,
        tools=tools,
        default_output_mode=options.default_output_mode,
        state="generated",
        module=module,
        launcher_path=launcher_path,
    )
