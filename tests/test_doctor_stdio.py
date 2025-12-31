import json
import os
import subprocess
import sys
from pathlib import Path


def test_doctor_stdio_quickstart() -> None:
    cmd = [
        sys.executable,
        "-m",
        "toolanything.cli",
        "doctor",
        "--mode",
        "stdio",
        "--tools",
        "examples.quickstart.tools",
        "--json",
        "--timeout",
        "5",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    steps = {step["name"]: step for step in report["steps"]}
    assert steps["transport"]["status"] == "PASS"
    assert steps["initialize"]["status"] == "PASS"
    assert steps["tools/list"]["status"] == "PASS"
    assert steps["tools/call"]["status"] == "PASS"
