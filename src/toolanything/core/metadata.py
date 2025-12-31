"""工具 metadata 正規化與定義。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Tuple


def _normalize_tags(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ToolMetadata:
    cost: Optional[float] = None
    latency_hint_ms: Optional[int] = None
    side_effect: Optional[bool] = None
    category: Optional[str] = None
    tags: Tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)


def normalize_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    tags: Iterable[str] | None = None,
) -> ToolMetadata:
    """將舊有 dict metadata 轉成標準化視圖，未知欄位保留在 extra。"""

    raw = dict(metadata or {})
    cost = _safe_float(raw.pop("cost", None))
    latency_hint_ms = _safe_int(raw.pop("latency_hint_ms", None))
    side_effect = raw.pop("side_effect", None)
    category = raw.pop("category", None)
    metadata_tags = _normalize_tags(raw.pop("tags", None))
    combined_tags = tuple(dict.fromkeys((*metadata_tags, *(tags or ()))))

    return ToolMetadata(
        cost=cost,
        latency_hint_ms=latency_hint_ms,
        side_effect=side_effect if side_effect is not None else None,
        category=str(category) if category is not None else None,
        tags=combined_tags,
        extra=raw,
    )
