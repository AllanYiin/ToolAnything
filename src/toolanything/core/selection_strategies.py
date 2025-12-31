"""工具搜尋策略介面與預設實作。"""
from __future__ import annotations

import difflib
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from .metadata import normalize_metadata
from .models import ToolSpec


FailureScoreFunc = Callable[..., float]


@dataclass(frozen=True)
class SelectionOptions:
    query: str = ""
    tags: Optional[list[str]] = None
    prefix: Optional[str] = None
    top_k: int = 10
    sort_by_failure: bool = True
    max_cost: Optional[float] = None
    latency_budget_ms: Optional[int] = None
    allow_side_effects: Optional[bool] = None
    categories: Optional[list[str]] = None
    use_metadata_ranking: bool = False


class BaseToolSelectionStrategy:
    """策略介面：依條件挑選並排序工具。"""

    def select(
        self,
        tools: Iterable[ToolSpec],
        *,
        options: SelectionOptions,
        failure_score: FailureScoreFunc,
        now: Optional[float] = None,
    ) -> list[ToolSpec]:
        raise NotImplementedError


class RuleBasedStrategy(BaseToolSelectionStrategy):
    """保留原有相似度 + tags/prefix + failure_score 的排序策略。"""

    def _similarity_score(self, query: str, spec: ToolSpec) -> float:
        if not query:
            return 0.0

        target = f"{spec.name} {spec.description} {' '.join(spec.tags)}"
        if query.lower() in target.lower():
            return 1.0
        return difflib.SequenceMatcher(None, query.lower(), target.lower()).ratio()

    def _filter_by_tags(self, specs: Iterable[ToolSpec], tags: Optional[List[str]]) -> list[ToolSpec]:
        if not tags:
            return list(specs)

        tag_set = set(tags)
        return [spec for spec in specs if tag_set.issubset(set(spec.tags))]

    def _filter_by_prefix(self, specs: Iterable[ToolSpec], prefix: Optional[str]) -> list[ToolSpec]:
        if not prefix:
            return list(specs)

        return [spec for spec in specs if spec.name.startswith(prefix)]

    def _filter_by_metadata(
        self,
        specs: Iterable[ToolSpec],
        *,
        max_cost: Optional[float],
        latency_budget_ms: Optional[int],
        allow_side_effects: Optional[bool],
        categories: Optional[list[str]],
    ) -> list[ToolSpec]:
        filtered = []
        category_set = set(categories or ())
        for spec in specs:
            meta = normalize_metadata(spec.metadata, tags=spec.tags)

            if max_cost is not None and meta.cost is not None and meta.cost > max_cost:
                continue
            if latency_budget_ms is not None and meta.latency_hint_ms is not None:
                if meta.latency_hint_ms > latency_budget_ms:
                    continue
            if allow_side_effects is False and meta.side_effect is True:
                continue
            if category_set and (meta.category not in category_set):
                continue

            filtered.append(spec)

        return filtered

    def select(
        self,
        tools: Iterable[ToolSpec],
        *,
        options: SelectionOptions,
        failure_score: FailureScoreFunc,
        now: Optional[float] = None,
    ) -> list[ToolSpec]:
        specs = self._filter_by_tags(tools, options.tags)
        specs = self._filter_by_prefix(specs, options.prefix)
        specs = self._filter_by_metadata(
            specs,
            max_cost=options.max_cost,
            latency_budget_ms=options.latency_budget_ms,
            allow_side_effects=options.allow_side_effects,
            categories=options.categories,
        )

        snapshot_time = now if now is not None else time.time()
        scored = []
        for spec in specs:
            similarity = self._similarity_score(options.query, spec)
            failure = failure_score(spec.name, now=snapshot_time)
            metadata = normalize_metadata(spec.metadata, tags=spec.tags)
            cost_sort = metadata.cost if metadata.cost is not None else float("inf")
            latency_sort = (
                metadata.latency_hint_ms if metadata.latency_hint_ms is not None else float("inf")
            )
            scored.append((spec, similarity, failure, cost_sort, latency_sort))

        if options.use_metadata_ranking:
            scored.sort(
                key=lambda item: (
                    -item[1],
                    item[2] if options.sort_by_failure else 0,
                    item[3],
                    item[4],
                    item[0].name,
                )
            )
        else:
            scored.sort(
                key=lambda item: (
                    -item[1],
                    item[2] if options.sort_by_failure else 0,
                    item[0].name,
                )
            )

        return [spec for spec, *_ in scored[: options.top_k]]


class HybridStrategy(BaseToolSelectionStrategy):
    """混合策略骨架：先 rule-based 篩選，再用 metadata 做二次排序。"""

    def __init__(self, base: BaseToolSelectionStrategy | None = None) -> None:
        self.base = base or RuleBasedStrategy()

    def select(
        self,
        tools: Iterable[ToolSpec],
        *,
        options: SelectionOptions,
        failure_score: FailureScoreFunc,
        now: Optional[float] = None,
    ) -> list[ToolSpec]:
        base_options = SelectionOptions(
            query=options.query,
            tags=options.tags,
            prefix=options.prefix,
            top_k=options.top_k,
            sort_by_failure=options.sort_by_failure,
        )
        candidates = self.base.select(
            tools,
            options=base_options,
            failure_score=failure_score,
            now=now,
        )

        if not options.use_metadata_ranking and not any(
            [
                options.max_cost,
                options.latency_budget_ms,
                options.allow_side_effects is False,
                options.categories,
            ]
        ):
            return candidates

        refined = RuleBasedStrategy().select(
            candidates,
            options=options,
            failure_score=failure_score,
            now=now,
        )
        return refined
