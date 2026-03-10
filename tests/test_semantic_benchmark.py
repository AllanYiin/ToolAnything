from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from examples.tool_selection.semantic_benchmark import (
    JsonlDatasetAdapter,
    describe_documents,
    run_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]


def test_semantic_benchmark_full_profile_beats_name_only_for_fake_backend():
    name_only = run_benchmark(
        backend="fake",
        profile="name-only",
        dataset="synthetic",
        split="mixed",
        tool_doc_langs=("en", "zh"),
        lexical_weight=0.0,
    )
    full = run_benchmark(
        backend="fake",
        profile="full",
        dataset="synthetic",
        split="mixed",
        tool_doc_langs=("en", "zh"),
        lexical_weight=0.0,
    )

    assert "hit_rate=1/5 (20.00%)" in name_only
    assert "hit_rate=5/5 (100.00%)" in full


def test_bilingual_tool_documents_improve_cross_lingual_retrieval():
    english_docs = run_benchmark(
        backend="fake",
        profile="full",
        dataset="synthetic",
        split="cross-zh-en",
        tool_doc_langs=("en",),
        lexical_weight=0.0,
    )
    bilingual_docs = run_benchmark(
        backend="fake",
        profile="full",
        dataset="synthetic",
        split="cross-zh-en",
        tool_doc_langs=("en", "zh"),
        lexical_weight=0.0,
    )

    assert "hit_rate=1/5 (20.00%)" in english_docs
    assert "hit_rate=5/5 (100.00%)" in bilingual_docs


def test_describe_documents_shows_language_variants():
    output = describe_documents(profile="name-description", tool_doc_langs=("en", "zh"))
    assert "tool_doc_langs=en,zh" in output
    assert "[catalog.send_email::en]" in output
    assert "[catalog.send_email::zh]" in output


def test_jsonl_dataset_adapter_filters_by_split(tmp_path):
    dataset_path = tmp_path / "cases.jsonl"
    rows = [
        {
            "split": "eval",
            "query": "send an email",
            "expected": "catalog.send_email",
            "query_lang": "en",
            "tools": [
                {
                    "name": "catalog.send_email",
                    "description": "Send an email notification",
                    "parameters": {"type": "object", "properties": {"to": {"type": "string"}}},
                }
            ],
        },
        {"split": "train", "query": "摘要一段文字", "expected": "catalog.summarize", "query_lang": "zh"},
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )

    adapter = JsonlDatasetAdapter(dataset_path)
    eval_rows = adapter.load_cases("eval")
    assert len(eval_rows) == 1
    assert eval_rows[0].expected == "catalog.send_email"
    assert eval_rows[0].tools[0].name == "catalog.send_email"


def test_jsonl_case_specific_tools_drive_retrieval(tmp_path):
    dataset_path = tmp_path / "bfcl_eval.jsonl"
    rows = [
        {
            "split": "eval",
            "query": "please send an email to the recipient",
            "expected": "send_email",
            "query_lang": "en",
            "tools": [
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
                        "required": ["to", "subject", "body"],
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
        }
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )

    output = run_benchmark(
        backend="fake",
        profile="full",
        dataset="jsonl",
        split="eval",
        dataset_path=str(dataset_path),
        tool_doc_langs=("en",),
        lexical_weight=0.0,
    )

    assert "expected=send_email | hit=True" in output
    assert "hit_rate=1/1 (100.00%)" in output


def test_semantic_benchmark_example_runs_as_script():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "examples.tool_selection.semantic_benchmark",
            "--backend",
            "fake",
            "--profile",
            "full",
            "--dataset",
            "synthetic",
            "--split",
            "cross-zh-en",
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
    assert "dataset=synthetic" in completed.stdout
    assert "split=cross-zh-en" in completed.stdout
    assert "tool_doc_langs=en,zh" in completed.stdout
    assert "lexical_weight=0.0" in completed.stdout
    assert "hit_rate=5/5 (100.00%)" in completed.stdout
