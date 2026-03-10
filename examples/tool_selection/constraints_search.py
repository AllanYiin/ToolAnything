"""Tool selection: 用 constraints 篩選工具的跨平台範例。"""
from __future__ import annotations

from pathlib import Path

from .catalog_shared import build_registry
from toolanything.core.failure_log import FailureLogManager
from toolanything.core.tool_search import ToolSearchTool


def show(searcher: ToolSearchTool, title: str, **kwargs) -> None:
    print(f"\n== {title}")
    for spec in searcher.search(**kwargs):
        meta = spec.normalized_metadata()
        print(
            f"{spec.name} cost={meta.cost} latency={meta.latency_hint_ms} "
            f"side_effect={meta.side_effect} category={meta.category}"
        )


def main() -> None:
    registry = build_registry()
    failure_log = FailureLogManager(Path(".tool_failures.json"))
    searcher = ToolSearchTool(registry, failure_log)

    show(searcher, "max-cost=0.02", max_cost=0.02)
    show(searcher, "latency-budget-ms=500", latency_budget_ms=500)
    show(searcher, "allow-side-effects=False", allow_side_effects=False)
    show(searcher, "category=finance", categories=["finance"])


if __name__ == "__main__":
    main()
