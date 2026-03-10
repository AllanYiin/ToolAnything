"""OpenAI function tool 名稱正規化工具。"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

OPENAI_FUNCTION_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_openai_function_name(name: str) -> bool:
    """檢查名稱是否符合 OpenAI function tool 限制。"""

    return bool(OPENAI_FUNCTION_NAME_RE.fullmatch(name))


def build_openai_name_mappings(names: Iterable[str]) -> tuple[dict[str, str], dict[str, str]]:
    """建立原始工具名稱與 OpenAI 可接受名稱的雙向映射。"""

    ordered_names = list(dict.fromkeys(names))
    original_to_openai: dict[str, str] = {}
    openai_to_original: dict[str, str] = {}

    for name in ordered_names:
        if is_valid_openai_function_name(name):
            original_to_openai[name] = name
            openai_to_original[name] = name

    for name in ordered_names:
        if name in original_to_openai:
            continue
        base_name = _slugify_for_openai(name)
        candidate = _dedupe_openai_name(base_name, original=name, used=openai_to_original)
        original_to_openai[name] = candidate
        openai_to_original[candidate] = name

    return original_to_openai, openai_to_original


def _slugify_for_openai(name: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_-")
    if not compact:
        return "tool"
    if len(compact) <= 64:
        return compact
    return compact[:64].rstrip("_-") or "tool"


def _dedupe_openai_name(base_name: str, *, original: str, used: dict[str, str]) -> str:
    if base_name not in used:
        return base_name

    digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:10]
    trimmed = base_name[: max(1, 64 - len(digest) - 1)].rstrip("_-") or "tool"
    candidate = f"{trimmed}_{digest}"
    if candidate not in used:
        return candidate

    counter = 1
    while True:
        suffix = hashlib.sha1(f"{original}:{counter}".encode("utf-8")).hexdigest()[:10]
        trimmed = base_name[: max(1, 64 - len(suffix) - 1)].rstrip("_-") or "tool"
        candidate = f"{trimmed}_{suffix}"
        if candidate not in used:
            return candidate
        counter += 1
