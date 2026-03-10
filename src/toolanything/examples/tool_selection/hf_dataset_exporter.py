"""Export Hugging Face dataset splits to local JSONL or JSON files."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any, Callable


class OptionalDependencyNotAvailable(RuntimeError):
    """Raised when optional dataset-export dependencies are missing."""


def export_dataset_split(
    *,
    dataset_id: str,
    split: str,
    output_path: str | Path,
    config_name: str | None = None,
    limit: int | None = None,
    file_format: str = "jsonl",
    cache_dir: str | None = None,
    module_loader: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    datasets = _load_datasets_module(module_loader)
    dataset = datasets.load_dataset(dataset_id, config_name, split=split, cache_dir=cache_dir)

    rows = []
    for index, row in enumerate(dataset):
        if limit is not None and index >= limit:
            break
        rows.append(dict(row))

    output = Path(output_path)
    if file_format == "jsonl":
        output.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
            encoding="utf-8",
        )
    elif file_format == "json":
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {file_format}")

    return {
        "dataset_id": dataset_id,
        "config_name": config_name,
        "split": split,
        "rows": len(rows),
        "output_path": str(output),
        "format": file_format,
    }


def _load_datasets_module(module_loader: Callable[[str], Any] | None) -> Any:
    loader = module_loader or importlib.import_module
    try:
        return loader("datasets")
    except ImportError as exc:
        raise OptionalDependencyNotAvailable(
            "Hugging Face dataset export requires the optional dependency 'datasets'. "
            "Install it only when needed, for example: python -m pip install datasets"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a Hugging Face dataset split to a local file.")
    parser.add_argument(
        "--dataset-id",
        required=True,
        help="Hugging Face dataset id, for example gorilla-llm/Berkeley-Function-Calling-Leaderboard",
    )
    parser.add_argument("--split", required=True, help="Dataset split, for example eval or train")
    parser.add_argument("--output", required=True, help="Destination JSONL/JSON file path")
    parser.add_argument("--config", default=None, help="Optional dataset config name")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for quick sampling")
    parser.add_argument(
        "--format",
        dest="file_format",
        choices=["jsonl", "json"],
        default="jsonl",
    )
    parser.add_argument("--cache-dir", default=None, help="Optional Hugging Face cache directory")
    args = parser.parse_args()

    result = export_dataset_split(
        dataset_id=args.dataset_id,
        split=args.split,
        output_path=args.output,
        config_name=args.config,
        limit=args.limit,
        file_format=args.file_format,
        cache_dir=args.cache_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
