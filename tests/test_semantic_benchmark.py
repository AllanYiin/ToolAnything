from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from toolanything.examples.tool_selection.semantic_benchmark import run_benchmark


ROOT = Path(__file__).resolve().parents[1]


def test_semantic_benchmark_full_profile_beats_name_only_for_fake_backend():
    name_only = run_benchmark(backend="fake", profile="name-only")
    full = run_benchmark(backend="fake", profile="full")

    assert "hit_rate=3/5 (60.00%)" in name_only
    assert "hit_rate=5/5 (100.00%)" in full


def test_semantic_benchmark_example_runs_as_script():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "toolanything.examples.tool_selection.semantic_benchmark",
            "--backend",
            "fake",
            "--profile",
            "full",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "backend=fake" in completed.stdout
    assert "profile=full" in completed.stdout
    assert "hit_rate=5/5 (100.00%)" in completed.stdout
