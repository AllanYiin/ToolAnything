#!/usr/bin/env bash
set -euo pipefail

python -m examples.tool_selection.constraints_search

# 預期輸出片段：
# == max-cost=0.02
# catalog.summarize cost=0.02 latency=800 side_effect=False category=nlp
# catalog.calculate_tax cost=0.01 latency=60 side_effect=False category=finance
