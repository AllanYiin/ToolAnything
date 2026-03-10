"""Tool selection: 自訂策略並注入 ToolSearchTool。"""
from __future__ import annotations

from pathlib import Path

from .catalog_shared import build_registry
from toolanything.core.failure_log import FailureLogManager
from toolanything.core.metadata import normalize_metadata
from toolanything.core.selection_strategies import (
    BaseToolSelectionStrategy,
    RuleBasedStrategy,
    SelectionOptions,
)
from toolanything.core.tool_search import ToolSearchTool


class CheapestFirstStrategy(BaseToolSelectionStrategy):
    """示範策略：先用 baseline 挑出候選，再改成成本與延遲優先。"""

    def __init__(self, base: BaseToolSelectionStrategy | None = None) -> None:
        self.base = base or RuleBasedStrategy()

    def select(self, tools, *, options: SelectionOptions, failure_score, now=None):
        pool = list(tools)
        candidates = self.base.select(
            pool,
            options=SelectionOptions(
                query=options.query,
                tags=options.tags,
                prefix=options.prefix,
                top_k=options.top_k,
                sort_by_failure=options.sort_by_failure,
                max_cost=options.max_cost,
                latency_budget_ms=options.latency_budget_ms,
                allow_side_effects=options.allow_side_effects,
                categories=options.categories,
                use_metadata_ranking=False,
            ),
            failure_score=failure_score,
            now=now,
        )
        scored = []
        for spec in candidates:
            meta = normalize_metadata(spec.metadata, tags=spec.tags)
            cost = meta.cost if meta.cost is not None else float("inf")
            latency = meta.latency_hint_ms if meta.latency_hint_ms is not None else float("inf")
            failure = failure_score(spec.name, now=now)
            scored.append((spec, cost, latency, failure))

        scored.sort(
            key=lambda item: (
                item[1],
                item[2],
                item[3] if options.sort_by_failure else 0,
                item[0].name,
            )
        )
        return [spec for spec, *_ in scored[: options.top_k]]


def main() -> None:
    registry = build_registry()
    failure_log = FailureLogManager(Path(".tool_failures.json"))
    default_searcher = ToolSearchTool(registry, failure_log)
    cheapest_searcher = ToolSearchTool(registry, failure_log, strategy=CheapestFirstStrategy())

    query = "文件翻譯"
    options = {
        "query": query,
        "categories": ["nlp"],
        "allow_side_effects": False,
        "top_k": 2,
    }

    default_results = default_searcher.search(**options)
    custom_results = cheapest_searcher.search(**options)

    print(f"查詢條件：query={query!r}, categories=['nlp'], allow_side_effects=False")
    print()
    print("預設策略結果（相似度/失敗分數優先）：")
    for spec in default_results:
        meta = spec.normalized_metadata()
        print(f"- {spec.name}: cost={meta.cost}, latency={meta.latency_hint_ms}")

    print()
    print("自訂策略結果（保留相同篩選，但改成成本/延遲優先）：")
    for spec in custom_results:
        meta = spec.normalized_metadata()
        print(f"- {spec.name}: cost={meta.cost}, latency={meta.latency_hint_ms}")


if __name__ == "__main__":
    main()
