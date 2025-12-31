#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from pathlib import Path

from examples.tool_selection.01_metadata_catalog import build_registry
from toolanything.core.failure_log import FailureLogManager
from toolanything.core.tool_search import ToolSearchTool

registry = build_registry()
failure_log = FailureLogManager(Path(".tool_failures.json"))
searcher = ToolSearchTool(registry, failure_log)


def show(title: str, **kwargs) -> None:
    print(f"\n== {title}")
    for spec in searcher.search(**kwargs):
        meta = spec.normalized_metadata()
        print(
            f"{spec.name} cost={meta.cost} latency={meta.latency_hint_ms} "
            f"side_effect={meta.side_effect} category={meta.category}"
        )


show("max-cost=0.02", max_cost=0.02)
show("latency-budget-ms=500", latency_budget_ms=500)
show("allow-side-effects=False", allow_side_effects=False)
show("category=finance", categories=["finance"])
PY

# 預期輸出片段：
# == max-cost=0.02
# catalog.summarize cost=0.02 latency=800 side_effect=False category=nlp
# catalog.calculate_tax cost=0.01 latency=60 side_effect=False category=finance
