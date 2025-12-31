"""Tool selection: 自訂策略並注入 ToolSearchTool。"""
from __future__ import annotations

from pathlib import Path

from examples.tool_selection.01_metadata_catalog import build_registry
from toolanything.core.failure_log import FailureLogManager
from toolanything.core.metadata import normalize_metadata
from toolanything.core.selection_strategies import BaseToolSelectionStrategy, SelectionOptions
from toolanything.core.tool_search import ToolSearchTool


class CheapestFirstStrategy(BaseToolSelectionStrategy):
    """示範策略：優先成本低、延遲低的工具。"""

    def select(self, tools, *, options: SelectionOptions, failure_score, now=None):
        candidates = list(tools)
        scored = []
        for spec in candidates:
            meta = normalize_metadata(spec.metadata, tags=spec.tags)
            cost = meta.cost if meta.cost is not None else float("inf")
            latency = meta.latency_hint_ms if meta.latency_hint_ms is not None else float("inf")
            scored.append((spec, cost, latency))
        scored.sort(key=lambda item: (item[1], item[2], item[0].name))
        return [spec for spec, *_ in scored[: options.top_k]]


def main() -> None:
    registry = build_registry()
    failure_log = FailureLogManager(Path(".tool_failures.json"))
    searcher = ToolSearchTool(registry, failure_log, strategy=CheapestFirstStrategy())

    results = searcher.search(query="", top_k=3)
    print("自訂策略結果（成本/延遲優先）：")
    for spec in results:
        meta = spec.normalized_metadata()
        print(f"- {spec.name}: cost={meta.cost}, latency={meta.latency_hint_ms}")


if __name__ == "__main__":
    main()
