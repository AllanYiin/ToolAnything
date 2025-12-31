"""提供工具搜尋與排序功能。"""
from __future__ import annotations

from typing import Optional

from .failure_log import FailureLogManager
from .models import ToolSpec
from .registry import ToolRegistry
from .selection_strategies import (
    BaseToolSelectionStrategy,
    RuleBasedStrategy,
    SelectionOptions,
)


class ToolSearchTool:
    """支援依名稱、描述與標籤搜尋工具，並可依失敗分數排序。"""

    def __init__(
        self,
        registry: ToolRegistry,
        failure_log: FailureLogManager,
        strategy: BaseToolSelectionStrategy | None = None,
    ) -> None:
        self.registry = registry
        self.failure_log = failure_log
        self.strategy = strategy or RuleBasedStrategy()

    def search(
        self,
        query: str = "",
        tags: Optional[list[str]] = None,
        prefix: Optional[str] = None,
        top_k: int = 10,
        sort_by_failure: bool = True,
        max_cost: Optional[float] = None,
        latency_budget_ms: Optional[int] = None,
        allow_side_effects: Optional[bool] = None,
        categories: Optional[list[str]] = None,
        use_metadata_ranking: Optional[bool] = None,
        *,
        now: Optional[float] = None,
    ) -> list[ToolSpec]:
        specs = self.registry.list()
        auto_metadata_ranking = use_metadata_ranking
        if auto_metadata_ranking is None:
            auto_metadata_ranking = any(
                [
                    max_cost is not None,
                    latency_budget_ms is not None,
                    allow_side_effects is not None,
                    categories,
                ]
            )

        options = SelectionOptions(
            query=query,
            tags=tags,
            prefix=prefix,
            top_k=top_k,
            sort_by_failure=sort_by_failure,
            max_cost=max_cost,
            latency_budget_ms=latency_budget_ms,
            allow_side_effects=allow_side_effects,
            categories=categories,
            use_metadata_ranking=auto_metadata_ranking,
        )

        return self.strategy.select(
            specs,
            options=options,
            failure_score=self.failure_log.failure_score,
            now=now,
        )


def build_search_tool(searcher: ToolSearchTool):
    """生成可註冊給 LLM 的搜尋工具函式。"""

    def search_tool(
        query: str = "",
        tags: Optional[list[str]] = None,
        prefix: Optional[str] = None,
        top_k: int = 10,
        max_cost: Optional[float] = None,
        latency_budget_ms: Optional[int] = None,
        allow_side_effects: Optional[bool] = None,
        categories: Optional[list[str]] = None,
    ) -> list[dict[str, object]]:
        """根據名稱、描述或標籤搜尋可用工具，會將近期失敗較多的項目排後。"""

        results = searcher.search(
            query=query,
            tags=tags,
            prefix=prefix,
            top_k=top_k,
            max_cost=max_cost,
            latency_budget_ms=latency_budget_ms,
            allow_side_effects=allow_side_effects,
            categories=categories,
        )
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "tags": list(spec.tags),
                "cost": spec.normalized_metadata().cost,
                "latency_hint_ms": spec.normalized_metadata().latency_hint_ms,
                "side_effect": spec.normalized_metadata().side_effect,
                "category": spec.normalized_metadata().category,
            }
            for spec in results
        ]

    return search_tool
