"""Convert BFCL-style tool calling datasets into retrieval JSONL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Iterable


_CALL_NAME_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]{0,127})\s*\(")


def load_records(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    if file_path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    records.append(json.loads(stripped))
        return records

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "examples"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported dataset payload in {file_path}")


def convert_records(
    records: Iterable[dict[str, Any]],
    *,
    split: str,
    query_lang: str = "auto",
    single_tool_only: bool = True,
    fallback_to_single_tool: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    converted: list[dict[str, Any]] = []
    stats = {
        "seen": 0,
        "kept": 0,
        "skipped_missing_query": 0,
        "skipped_missing_tools": 0,
        "skipped_missing_expected": 0,
        "skipped_multi_tool": 0,
    }

    for row in records:
        stats["seen"] += 1
        query = extract_query(row)
        if not query:
            stats["skipped_missing_query"] += 1
            continue

        tools = extract_tools(row)
        if not tools:
            stats["skipped_missing_tools"] += 1
            continue

        expected_names = extract_expected_tool_names(row)
        expected_names = [name for name in expected_names if name]
        if not expected_names and fallback_to_single_tool and len(tools) == 1:
            expected_names = [str(tools[0]["name"])]
        if not expected_names:
            stats["skipped_missing_expected"] += 1
            continue

        unique_expected = list(dict.fromkeys(expected_names))
        if single_tool_only and len(unique_expected) != 1:
            stats["skipped_multi_tool"] += 1
            continue

        resolved_query_lang = infer_query_lang(query) if query_lang == "auto" else query_lang
        converted.append(
            {
                "split": split,
                "query": query,
                "expected": unique_expected[0],
                "query_lang": resolved_query_lang,
                "tools": tools,
            }
        )
        stats["kept"] += 1

    return converted, stats


def write_jsonl(rows: Iterable[dict[str, Any]], path: str | Path) -> None:
    file_path = Path(path)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    file_path.write_text("\n".join(lines), encoding="utf-8")


def extract_query(row: dict[str, Any]) -> str:
    for key in ("question", "query", "prompt", "user_query"):
        if key in row:
            return _flatten_text(row[key]).strip()
    return ""


def extract_tools(row: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("function", "functions", "tools", "tool", "candidate_tools"):
        if key not in row:
            continue
        parsed = _parse_jsonish(row[key])
        tools = _normalize_tools(parsed)
        if tools:
            return tools
    return []


def extract_expected_tool_names(row: dict[str, Any]) -> list[str]:
    for key in ("ground_truth", "answer", "answers", "expected", "tool_name"):
        if key in row:
            names = _extract_tool_names(row[key])
            if names:
                return names
    return []


def infer_query_lang(text: str) -> str:
    for character in text:
        codepoint = ord(character)
        if 0x4E00 <= codepoint <= 0x9FFF:
            return "zh"
    return "en"


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_flatten_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if "content" in value:
            return _flatten_text(value["content"])
        if "message" in value:
            return _flatten_text(value["message"])
        if "text" in value:
            return _flatten_text(value["text"])
        if "role" in value and value.get("role") == "user":
            return _flatten_text(value.get("content"))
        parts = [_flatten_text(item) for item in value.values()]
        return "\n".join(part for part in parts if part)
    return str(value)


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped[0] in "[{":
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _normalize_tools(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        tools: list[dict[str, Any]] = []
        for item in raw:
            tools.extend(_normalize_tools(item))
        return tools

    if isinstance(raw, dict):
        if raw.get("type") == "function" and isinstance(raw.get("function"), dict):
            return _normalize_tools(raw["function"])
        if "name" in raw:
            return [
                {
                    "name": str(raw["name"]),
                    "description": str(raw.get("description", "")),
                    "parameters": dict(raw.get("parameters") or raw.get("input_schema") or {}),
                    "tags": list(raw.get("tags", [])) if isinstance(raw.get("tags"), list) else [],
                    "metadata": dict(raw.get("metadata", {})) if isinstance(raw.get("metadata"), dict) else {},
                }
            ]
        for key in ("functions", "tools"):
            if key in raw:
                return _normalize_tools(raw[key])
    return []


def _extract_tool_names(raw: Any) -> list[str]:
    parsed = _parse_jsonish(raw)
    if isinstance(parsed, list):
        names: list[str] = []
        for item in parsed:
            names.extend(_extract_tool_names(item))
        return names

    if isinstance(parsed, dict):
        for key in ("name", "tool_name", "api_name", "function"):
            value = parsed.get(key)
            if isinstance(value, str):
                return [value]
            if isinstance(value, dict):
                nested = _extract_tool_names(value)
                if nested:
                    return nested
        if "tool_calls" in parsed:
            return _extract_tool_names(parsed["tool_calls"])
        if "content" in parsed:
            return _extract_tool_names(parsed["content"])
        return []

    if isinstance(parsed, str):
        stripped = parsed.strip()
        if not stripped:
            return []
        match = _CALL_NAME_RE.search(stripped)
        if match:
            return [match.group(1)]
        return []

    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert BFCL-style rows into retrieval JSONL.")
    parser.add_argument("--input", required=True, help="Path to a local JSON or JSONL dataset file.")
    parser.add_argument("--output", required=True, help="Output JSONL path.")
    parser.add_argument("--split", default="eval", help="Split label written into the output rows.")
    parser.add_argument(
        "--query-lang",
        default="auto",
        choices=["auto", "en", "zh"],
        help="Query language label. Use auto to infer from the query text.",
    )
    parser.add_argument(
        "--allow-multi-tool",
        action="store_true",
        help="Keep rows with multiple expected tools by taking the first one. Default is to skip them.",
    )
    args = parser.parse_args()

    rows = load_records(args.input)
    converted, stats = convert_records(
        rows,
        split=args.split,
        query_lang=args.query_lang,
        single_tool_only=not args.allow_multi_tool,
        fallback_to_single_tool=True,
    )
    write_jsonl(converted, args.output)
    print(json.dumps({"output": str(args.output), **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
