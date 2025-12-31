"""Run tool search against the quickstart registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from toolanything.core import FailureLogManager, ToolRegistry, ToolSearchTool
from toolanything.runtime.serve import load_tool_module


def main() -> None:
    parser = argparse.ArgumentParser(description="ToolAnything Quickstart Search")
    parser.add_argument("--query", default="", help="搜尋關鍵字")
    parser.add_argument("--tags", nargs="*", default=None, help="標籤條件")
    parser.add_argument("--top-k", type=int, default=5, help="回傳筆數")
    args = parser.parse_args()

    module_path = Path(__file__).resolve().parent / "tools.py"
    load_tool_module(str(module_path))

    registry = ToolRegistry.global_instance()
    failure_log = FailureLogManager()
    searcher = ToolSearchTool(registry, failure_log)

    results = searcher.search(query=args.query, tags=args.tags, top_k=args.top_k)
    for spec in results:
        print(
            json.dumps(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "tags": list(spec.tags),
                    "metadata": {
                        "cost": spec.normalized_metadata().cost,
                        "latency_hint_ms": spec.normalized_metadata().latency_hint_ms,
                        "side_effect": spec.normalized_metadata().side_effect,
                        "category": spec.normalized_metadata().category,
                    },
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
