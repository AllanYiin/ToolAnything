from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from examples.tool_selection.bfcl_converter import (
    convert_records,
    extract_expected_tool_names,
    extract_query,
    extract_tools,
)


ROOT = Path(__file__).resolve().parents[1]


def test_extract_query_handles_message_lists():
    row = {
        "question": [
            {"role": "system", "content": "You are a tool caller."},
            {"role": "user", "content": "Send an email to Alice."},
        ]
    }
    assert "Send an email to Alice." in extract_query(row)


def test_extract_tools_normalizes_openai_wrapped_functions():
    row = {
        "function": [
            {
                "type": "function",
                "function": {
                    "name": "send_email",
                    "description": "Send an email notification",
                    "parameters": {"type": "object", "properties": {"to": {"type": "string"}}},
                },
            }
        ]
    }
    tools = extract_tools(row)
    assert tools == [
        {
            "name": "send_email",
            "description": "Send an email notification",
            "parameters": {"type": "object", "properties": {"to": {"type": "string"}}},
            "tags": [],
            "metadata": {},
        }
    ]


def test_extract_expected_tool_names_from_string_call():
    row = {"ground_truth": "send_email(to='alice@example.com', subject='hi', body='hello')"}
    assert extract_expected_tool_names(row) == ["send_email"]


def test_convert_records_skips_multi_tool_rows_by_default():
    rows = [
        {
            "question": "send an email",
            "function": [{"name": "send_email", "description": "Send email", "parameters": {}}],
            "ground_truth": ["send_email(to='a')", "log_event(action='email')"],
        }
    ]
    converted, stats = convert_records(rows, split="eval")
    assert converted == []
    assert stats["skipped_multi_tool"] == 1


def test_convert_records_outputs_retrieval_ready_rows():
    rows = [
        {
            "question": "Send an email to Alice.",
            "function": json.dumps(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "send_email",
                            "description": "Send an email notification",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "to": {"type": "string"},
                                    "subject": {"type": "string"},
                                },
                            },
                        },
                    }
                ]
            ),
            "ground_truth": "send_email(to='alice@example.com', subject='hi')",
        }
    ]
    converted, stats = convert_records(rows, split="eval")
    assert stats["kept"] == 1
    assert converted[0]["expected"] == "send_email"
    assert converted[0]["query_lang"] == "en"
    assert converted[0]["tools"][0]["name"] == "send_email"


def test_convert_records_can_fallback_to_single_tool_when_ground_truth_missing():
    rows = [
        {
            "question": "Find the area of a triangle.",
            "function": [
                {
                    "name": "calculate_triangle_area",
                    "description": "Calculate triangle area",
                    "parameters": {"type": "object", "properties": {"base": {"type": "number"}}},
                }
            ],
        }
    ]
    converted, stats = convert_records(rows, split="eval")
    assert stats["kept"] == 1
    assert converted[0]["expected"] == "calculate_triangle_area"


def test_bfcl_converter_script_runs_end_to_end(tmp_path):
    source_path = tmp_path / "bfcl.json"
    output_path = tmp_path / "retrieval.jsonl"
    source_rows = [
        {
            "question": "請寄送電子郵件給 Bob",
            "function": [
                {
                    "name": "send_email",
                    "description": "寄送電子郵件通知",
                    "parameters": {"type": "object", "properties": {"to": {"type": "string"}}},
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
            "examples.tool_selection.bfcl_converter",
            "--input",
            str(source_path),
            "--output",
            str(output_path),
            "--split",
            "eval",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert output_path.exists()
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["expected"] == "send_email"
    assert rows[0]["query_lang"] == "zh"
