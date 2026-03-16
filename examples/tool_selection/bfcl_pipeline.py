"""One-command pipeline for BFCL-style retrieval benchmarking."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bfcl_converter import convert_records, load_records, write_records
from .hf_dataset_exporter import export_dataset_split
from .semantic_benchmark import run_benchmark


def run_pipeline(
    *,
    workdir: str | Path,
    split: str,
    backend: str,
    profile: str,
    tool_doc_langs: tuple[str, ...],
    lexical_weight: float,
    input_path: str | None = None,
    dataset_id: str | None = None,
    config_name: str | None = None,
    limit: int | None = None,
    cache_dir: str | None = None,
    query_lang: str = "auto",
    allow_multi_tool: bool = False,
) -> dict[str, Any]:
    output_dir = Path(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if dataset_id:
        raw_path = output_dir / "hf_export.json"
        export_summary = export_dataset_split(
            dataset_id=dataset_id,
            config_name=config_name,
            split=split,
            output_path=raw_path,
            limit=limit,
            file_format="json",
            cache_dir=cache_dir,
        )
    elif input_path:
        raw_path = Path(input_path)
        export_summary = None
    else:
        raise ValueError("Either input_path or dataset_id is required.")

    records = load_records(raw_path)
    converted_rows, convert_stats = convert_records(
        records,
        split=split,
        query_lang=query_lang,
        single_tool_only=not allow_multi_tool,
    )
    retrieval_path = output_dir / "retrieval_eval.json"
    write_records(converted_rows, retrieval_path, file_format="json")

    benchmark_output = run_benchmark(
        backend=backend,
        profile=profile,
        dataset="json",
        split=split,
        dataset_path=str(retrieval_path),
        tool_doc_langs=tool_doc_langs,
        lexical_weight=lexical_weight,
    )

    return {
        "workdir": str(output_dir),
        "raw_path": str(raw_path),
        "retrieval_path": str(retrieval_path),
        "export": export_summary,
        "convert": convert_stats,
        "benchmark": benchmark_output,
    }


def _parse_tool_doc_langs(raw: str) -> tuple[str, ...]:
    items = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not items:
        raise ValueError("tool_doc_langs must include at least one language")
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BFCL retrieval benchmark pipeline end-to-end.")
    parser.add_argument("--workdir", required=True, help="Directory for exported and converted files.")
    parser.add_argument("--split", default="eval", help="Dataset split label.")
    parser.add_argument("--backend", choices=["fake", "onnx"], default="fake")
    parser.add_argument("--profile", choices=["name-only", "name-description", "full"], default="full")
    parser.add_argument("--tool-doc-langs", default="en,zh")
    parser.add_argument("--lexical-weight", type=float, default=0.0)
    parser.add_argument("--input", default=None, help="Local BFCL-style JSON or JSONL file.")
    parser.add_argument("--dataset-id", default=None, help="Hugging Face dataset id to export first.")
    parser.add_argument("--config", default=None, help="Optional Hugging Face dataset config.")
    parser.add_argument("--limit", type=int, default=None, help="Optional export row limit when dataset-id is used.")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--query-lang", choices=["auto", "en", "zh"], default="auto")
    parser.add_argument("--allow-multi-tool", action="store_true")
    args = parser.parse_args()

    summary = run_pipeline(
        workdir=args.workdir,
        split=args.split,
        backend=args.backend,
        profile=args.profile,
        tool_doc_langs=_parse_tool_doc_langs(args.tool_doc_langs),
        lexical_weight=args.lexical_weight,
        input_path=args.input,
        dataset_id=args.dataset_id,
        config_name=args.config,
        limit=args.limit,
        cache_dir=args.cache_dir,
        query_lang=args.query_lang,
        allow_multi_tool=args.allow_multi_tool,
    )
    benchmark_output = summary.pop("benchmark")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print()
    print(benchmark_output)


if __name__ == "__main__":
    main()
