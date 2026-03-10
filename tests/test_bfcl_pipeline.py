from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from examples.tool_selection.bfcl_pipeline import run_pipeline


ROOT = Path(__file__).resolve().parents[1]


def test_bfcl_pipeline_runs_end_to_end_on_local_input(tmp_path):
    source_path = tmp_path / "bfcl.json"
    source_rows = [
        {
            "question": "Send an email to Alice.",
            "function": [
                {
                    "name": "send_email",
                    "description": "Send an email notification",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient"},
                            "subject": {"type": "string", "description": "Subject"},
                            "body": {"type": "string", "description": "Email body"},
                        },
                    },
                },
                {
                    "name": "estimate_tax",
                    "description": "Estimate tax amount",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Amount"},
                            "rate": {"type": "number", "description": "Tax rate"},
                        },
                    },
                },
            ],
            "ground_truth": "send_email(to='alice@example.com', subject='hi', body='hello')",
        }
    ]
    source_path.write_text(json.dumps(source_rows, ensure_ascii=False), encoding="utf-8")

    summary = run_pipeline(
        workdir=tmp_path / "artifacts",
        split="eval",
        backend="fake",
        profile="full",
        tool_doc_langs=("en",),
        lexical_weight=0.0,
        input_path=str(source_path),
    )

    assert summary["export"] is None
    assert summary["convert"]["kept"] == 1
    assert Path(summary["retrieval_path"]).exists()
    assert "hit_rate=1/1 (100.00%)" in summary["benchmark"]


def test_bfcl_pipeline_script_runs(tmp_path):
    source_path = tmp_path / "bfcl.json"
    source_rows = [
        {
            "question": "請寄送電子郵件給 Bob",
            "function": [
                {
                    "name": "send_email",
                    "description": "寄送電子郵件通知",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "收件者"},
                            "subject": {"type": "string", "description": "標題"},
                            "body": {"type": "string", "description": "內文"},
                        },
                    },
                }
            ],
            "ground_truth": [{"name": "send_email", "arguments": {"to": "bob@example.com"}}],
        }
    ]
    source_path.write_text(json.dumps(source_rows, ensure_ascii=False), encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "examples.tool_selection.bfcl_pipeline",
            "--workdir",
            str(tmp_path / "artifacts"),
            "--input",
            str(source_path),
            "--split",
            "eval",
            "--backend",
            "fake",
            "--profile",
            "full",
            "--tool-doc-langs",
            "en,zh",
            "--lexical-weight",
            "0",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "\"retrieval_path\"" in completed.stdout
    assert "hit_rate=1/1 (100.00%)" in completed.stdout
