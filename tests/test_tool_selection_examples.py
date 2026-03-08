from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from toolanything.core import FailureLogManager, ToolSearchTool


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "tool_selection"


def test_custom_strategy_example_runs_as_script():
    script = EXAMPLE_DIR / "03_custom_strategy.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "預設策略結果" in completed.stdout
    assert "自訂策略結果" in completed.stdout


def test_custom_strategy_preserves_constraints_and_only_changes_ranking():
    namespace: dict[str, object] = {"__file__": str(script := EXAMPLE_DIR / "03_custom_strategy.py")}
    exec(compile(script.read_text(encoding="utf-8"), str(script), "exec"), namespace)

    build_registry = namespace["build_registry"]
    strategy_cls = namespace["CheapestFirstStrategy"]

    registry = build_registry()
    baseline = ToolSearchTool(registry, FailureLogManager())
    custom = ToolSearchTool(registry, FailureLogManager(), strategy=strategy_cls())

    options = {
        "query": "文件翻譯",
        "categories": ["nlp"],
        "allow_side_effects": False,
        "top_k": 2,
    }

    baseline_names = [spec.name for spec in baseline.search(**options)]
    custom_names = [spec.name for spec in custom.search(**options)]

    assert baseline_names == ["catalog.translate_quality", "catalog.translate_fast"]
    assert custom_names == ["catalog.translate_fast", "catalog.translate_quality"]
