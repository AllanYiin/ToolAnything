"""CLI runtime adapter。"""
from __future__ import annotations

import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any

from .exceptions import (
    CLIArgumentValidationError,
    CLIOutputSerializationError,
    CLIUnsupportedFeatureError,
)
from .types import (
    CLIInvocationEnvelope,
    EXIT_ARG_VALIDATION_ERROR,
    EXIT_INTERRUPTED,
    EXIT_RUNTIME_INVOCATION_ERROR,
    EXIT_SUCCESS,
    EXIT_TOOL_EXECUTION_ERROR,
    EXIT_UNSUPPORTED_FEATURE,
)
from ..core.registry import ToolRegistry
from ..exceptions import ToolError


def _summarize_text_preview(path: Path, limit: int = 160) -> str:
    try:
        content = path.read_text(encoding="utf-8")
        compact = " ".join(content.split())
        return compact[:limit] + ("..." if len(compact) > limit else "")
    except Exception:
        return "binary or unreadable content"


def _artifact_preview(path: Path) -> dict[str, Any]:
    mime_type, _ = mimetypes.guess_type(path.name)
    summary = path.name
    if mime_type and (
        mime_type.startswith("text/")
        or mime_type == "application/json"
        or path.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}
    ):
        summary = _summarize_text_preview(path)
    return {
        "path": str(path),
        "mime_type": mime_type,
        "size_bytes": path.stat().st_size if path.exists() else None,
        "preview_summary": summary,
    }


def collect_artifacts(payload: Any) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                _visit(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _visit(item)
            return
        if not isinstance(value, str):
            return
        candidate = Path(value)
        if not candidate.exists() or not candidate.is_file():
            return
        resolved = str(candidate.resolve())
        if resolved in seen:
            return
        seen.add(resolved)
        artifacts.append(_artifact_preview(candidate))

    _visit(payload)
    return artifacts


def validate_path_arguments(arguments: dict[str, Any], *, path_fields: set[str]) -> None:
    for field in path_fields:
        if field not in arguments:
            continue
        value = arguments[field]
        if isinstance(value, str):
            path = Path(value)
            if not path.exists():
                raise CLIArgumentValidationError(f"找不到檔案路徑: {path}")


def validate_aspect_ratio(arguments: dict[str, Any], metadata: dict[str, Any]) -> None:
    cli_meta = metadata.get("cli", {})
    ratio_spec = cli_meta.get("aspect_ratio")
    if not ratio_spec:
        return

    width_key = ratio_spec.get("width", "width")
    height_key = ratio_spec.get("height", "height")
    original_width = ratio_spec.get("original_width")
    original_height = ratio_spec.get("original_height")
    if not original_width or not original_height:
        raise CLIUnsupportedFeatureError("aspect_ratio 設定缺少 original_width/original_height")
    width = arguments.get(width_key)
    height = arguments.get(height_key)
    if width is None or height is None:
        return
    if int(width) * int(original_height) != int(height) * int(original_width):
        raise CLIArgumentValidationError(
            "width and height would break original aspect ratio"
        )


async def invoke_via_registry(
    registry: ToolRegistry,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    output_mode: str,
    stream: bool,
) -> CLIInvocationEnvelope:
    try:
        result = await registry.invoke_tool_async(
            tool_name,
            arguments=arguments,
            stream=None,
        )
        return CLIInvocationEnvelope(
            ok=True,
            tool_name=tool_name,
            exit_code=EXIT_SUCCESS,
            output_mode="stream" if stream and output_mode == "text" else output_mode,
            result=result,
            artifacts=collect_artifacts({"arguments": arguments, "result": result}),
            meta={},
        )
    except ToolError as exc:
        exit_code = (
            EXIT_ARG_VALIDATION_ERROR
            if exc.error_type == "validation_error"
            else EXIT_TOOL_EXECUTION_ERROR
        )
        return CLIInvocationEnvelope(
            ok=False,
            tool_name=tool_name,
            exit_code=exit_code,
            output_mode=output_mode,
            error={
                "code": exc.error_type.upper(),
                "message": str(exc),
                "details": exc.data,
            },
        )
    except asyncio.CancelledError:
        return CLIInvocationEnvelope(
            ok=False,
            tool_name=tool_name,
            exit_code=EXIT_INTERRUPTED,
            output_mode=output_mode,
            error={"code": "INTERRUPTED", "message": "已中斷執行", "details": {}},
        )
    except Exception as exc:
        return CLIInvocationEnvelope(
            ok=False,
            tool_name=tool_name,
            exit_code=EXIT_RUNTIME_INVOCATION_ERROR,
            output_mode=output_mode,
            error={
                "code": "RUNTIME_INVOCATION_ERROR",
                "message": str(exc),
                "details": {},
            },
        )


def serialize_json_envelope(envelope: CLIInvocationEnvelope) -> str:
    payload = {
        "ok": envelope.ok,
        "tool_name": envelope.tool_name,
        "exit_code": envelope.exit_code,
        "result": envelope.result,
        "error": envelope.error,
        "artifacts": envelope.artifacts,
        "meta": envelope.meta,
    }
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except TypeError as exc:
        raise CLIOutputSerializationError("CLI JSON 輸出序列化失敗") from exc


def render_text_envelope(envelope: CLIInvocationEnvelope) -> str:
    if envelope.ok:
        if isinstance(envelope.result, (dict, list)):
            body = json.dumps(envelope.result, ensure_ascii=False, indent=2)
        else:
            body = str(envelope.result)
        artifact_lines = [
            f"- {artifact['path']} ({artifact.get('mime_type') or 'unknown'}, {artifact.get('size_bytes')})"
            for artifact in envelope.artifacts
        ]
        if artifact_lines:
            body = f"{body}\n\nArtifacts:\n" + "\n".join(artifact_lines)
        return body
    error = envelope.error or {}
    return f"[{error.get('code', 'ERROR')}] {error.get('message', '未知錯誤')}"


def envelope_exit_code(error: Exception) -> int:
    if isinstance(error, CLIArgumentValidationError):
        return EXIT_ARG_VALIDATION_ERROR
    if isinstance(error, CLIOutputSerializationError):
        return 6
    if isinstance(error, CLIUnsupportedFeatureError):
        return EXIT_UNSUPPORTED_FEATURE
    return EXIT_RUNTIME_INVOCATION_ERROR
