"""Export Hugging Face dataset splits or raw repo files to local JSON or JSONL files."""
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
    output_path: str | Path,
    split: str | None = None,
    config_name: str | None = None,
    repo_file: str | None = None,
    limit: int | None = None,
    file_format: str = "auto",
    cache_dir: str | None = None,
    module_loader: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    if repo_file:
        rows = _export_repo_file(
            dataset_id=dataset_id,
            repo_file=repo_file,
            limit=limit,
            cache_dir=cache_dir,
            module_loader=module_loader,
        )
    else:
        if split is None:
            raise ValueError("split is required when repo_file is not provided")
        datasets = _load_datasets_module(module_loader)
        dataset = datasets.load_dataset(dataset_id, config_name, split=split, cache_dir=cache_dir)
        rows = []
        for index, row in enumerate(dataset):
            if limit is not None and index >= limit:
                break
            rows.append(dict(row))

    output = Path(output_path)
    resolved_format = _resolve_file_format(output, file_format)
    if resolved_format == "jsonl":
        output.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
            encoding="utf-8",
        )
    elif resolved_format == "json":
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {resolved_format}")

    return {
        "dataset_id": dataset_id,
        "config_name": config_name,
        "split": split,
        "repo_file": repo_file,
        "rows": len(rows),
        "output_path": str(output),
        "format": resolved_format,
    }


def _resolve_file_format(output_path: Path, file_format: str) -> str:
    if file_format == "auto":
        return "jsonl" if output_path.suffix.lower() == ".jsonl" else "json"
    return file_format


def _load_datasets_module(module_loader: Callable[[str], Any] | None) -> Any:
    loader = module_loader or importlib.import_module
    try:
        return loader("datasets")
    except ImportError as exc:
        raise OptionalDependencyNotAvailable(
            "Hugging Face dataset export requires the optional dependency 'datasets'. "
            "Install it only when needed, for example: python -m pip install datasets"
        ) from exc


def _load_hf_hub_module(module_loader: Callable[[str], Any] | None) -> Any:
    loader = module_loader or importlib.import_module
    try:
        return loader("huggingface_hub")
    except ImportError as exc:
        raise OptionalDependencyNotAvailable(
            "Raw Hugging Face file export requires the optional dependency "
            "'huggingface-hub'. Install it only when needed, for example: "
            "python -m pip install huggingface-hub"
        ) from exc


def _export_repo_file(
    *,
    dataset_id: str,
    repo_file: str,
    limit: int | None,
    cache_dir: str | None,
    module_loader: Callable[[str], Any] | None,
) -> list[dict[str, Any]]:
    huggingface_hub = _load_hf_hub_module(module_loader)
    download_fn = getattr(huggingface_hub, "hf_hub_download", None)
    if download_fn is None:
        raise OptionalDependencyNotAvailable(
            "huggingface_hub.hf_hub_download could not be imported for raw dataset export."
        )

    local_path = download_fn(
        repo_id=dataset_id,
        repo_type="dataset",
        filename=repo_file,
        cache_dir=cache_dir,
    )
    rows = _load_rows_from_file(local_path)
    if limit is not None:
        return rows[:limit]
    return rows


def _load_rows_from_file(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".jsonl":
        return _load_rows_from_json_lines(file_path)

    content = file_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return _load_rows_from_json_lines(file_path)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "examples"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported raw dataset file payload: {file_path}")


def _load_rows_from_json_lines(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                payload = json.loads(stripped)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a Hugging Face dataset split or repo file to a local JSON file.")
    parser.add_argument(
        "--dataset-id",
        required=True,
        help="Hugging Face dataset id, for example gorilla-llm/Berkeley-Function-Calling-Leaderboard",
    )
    parser.add_argument("--split", default=None, help="Dataset split, for example eval or train")
    parser.add_argument(
        "--repo-file",
        default=None,
        help="Optional raw file inside the dataset repo, for example BFCL_v3_simple.json",
    )
    parser.add_argument("--output", required=True, help="Destination JSON/JSONL file path")
    parser.add_argument("--config", default=None, help="Optional dataset config name")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for quick sampling")
    parser.add_argument(
        "--format",
        dest="file_format",
        choices=["auto", "json", "jsonl"],
        default="auto",
    )
    parser.add_argument("--cache-dir", default=None, help="Optional Hugging Face cache directory")
    args = parser.parse_args()

    result = export_dataset_split(
        dataset_id=args.dataset_id,
        split=args.split,
        output_path=args.output,
        config_name=args.config,
        repo_file=args.repo_file,
        limit=args.limit,
        file_format=args.file_format,
        cache_dir=args.cache_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
