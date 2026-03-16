from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from examples.tool_selection.hf_dataset_exporter import (
    OptionalDependencyNotAvailable,
    export_dataset_split,
)


ROOT = Path(__file__).resolve().parents[1]


class _FakeDatasetsModule:
    @staticmethod
    def load_dataset(dataset_id, config_name, split, cache_dir=None):
        assert dataset_id == "demo/dataset"
        assert config_name == "default"
        assert split == "eval"
        assert cache_dir is None
        return [
            {"question": "one"},
            {"question": "two"},
            {"question": "three"},
        ]


def test_export_dataset_split_writes_json_by_default(tmp_path):
    output_path = tmp_path / "sample.json"
    result = export_dataset_split(
        dataset_id="demo/dataset",
        config_name="default",
        split="eval",
        output_path=output_path,
        limit=2,
        module_loader=lambda name: _FakeDatasetsModule if name == "datasets" else None,
    )

    rows = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert result["rows"] == 2
    assert result["format"] == "json"


def test_export_dataset_split_supports_raw_repo_file(tmp_path):
    source_path = tmp_path / "source.json"
    source_path.write_text(
        json.dumps([{"question": "one"}, {"question": "two"}], ensure_ascii=False),
        encoding="utf-8",
    )
    output_path = tmp_path / "sample.json"

    class _FakeHubModule:
        @staticmethod
        def hf_hub_download(repo_id, repo_type, filename, cache_dir=None):
            assert repo_id == "demo/dataset"
            assert repo_type == "dataset"
            assert filename == "BFCL_v3_simple.json"
            assert cache_dir is None
            return str(source_path)

    result = export_dataset_split(
        dataset_id="demo/dataset",
        repo_file="BFCL_v3_simple.json",
        output_path=output_path,
        limit=1,
        module_loader=lambda name: _FakeHubModule if name == "huggingface_hub" else None,
    )

    rows = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["question"] == "one"
    assert result["repo_file"] == "BFCL_v3_simple.json"


def test_export_dataset_split_still_supports_jsonl_output(tmp_path):
    output_path = tmp_path / "sample.jsonl"
    result = export_dataset_split(
        dataset_id="demo/dataset",
        config_name="default",
        split="eval",
        output_path=output_path,
        limit=2,
        file_format="jsonl",
        module_loader=lambda name: _FakeDatasetsModule if name == "datasets" else None,
    )

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert result["format"] == "jsonl"


def test_export_dataset_split_supports_json_lines_with_json_suffix(tmp_path):
    source_path = tmp_path / "source.json"
    source_path.write_text(
        '{"question":"one"}\n{"question":"two"}\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "sample.json"

    class _FakeHubModule:
        @staticmethod
        def hf_hub_download(repo_id, repo_type, filename, cache_dir=None):
            return str(source_path)

    result = export_dataset_split(
        dataset_id="demo/dataset",
        repo_file="BFCL_v3_simple.json",
        output_path=output_path,
        limit=2,
        module_loader=lambda name: _FakeHubModule if name == "huggingface_hub" else None,
    )

    rows = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[1]["question"] == "two"
    assert result["rows"] == 2


def test_export_dataset_split_raises_clear_error_without_dependency(tmp_path):
    try:
        export_dataset_split(
            dataset_id="demo/dataset",
            split="eval",
            output_path=tmp_path / "sample.json",
            module_loader=lambda _name: (_ for _ in ()).throw(ImportError("missing")),
        )
    except OptionalDependencyNotAvailable as exc:
        assert "datasets" in str(exc)
    else:
        raise AssertionError("expected OptionalDependencyNotAvailable")


def test_hf_dataset_exporter_script_runs(tmp_path):
    helper_path = tmp_path / "sitecustomize.py"
    helper_path.write_text(
        "import sys, types\n"
        "module = types.ModuleType('datasets')\n"
        "module.load_dataset = lambda dataset_id, config_name, split, cache_dir=None: ["
        "{'question': 'one'}, {'question': 'two'}]\n"
        "sys.modules['datasets'] = module\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "dataset.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + str(ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "examples.tool_selection.hf_dataset_exporter",
            "--dataset-id",
            "demo/dataset",
            "--config",
            "default",
            "--split",
            "eval",
            "--output",
            str(output_path),
            "--limit",
            "1",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert output_path.exists()
    rows = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_hf_dataset_exporter_script_supports_repo_file(tmp_path):
    source_path = tmp_path / "bfcl.json"
    source_path.write_text(json.dumps([{"question": "one"}, {"question": "two"}]), encoding="utf-8")
    helper_path = tmp_path / "sitecustomize.py"
    helper_path.write_text(
        "import sys, types\n"
        "module = types.ModuleType('huggingface_hub')\n"
        f"module.hf_hub_download = lambda repo_id, repo_type, filename, cache_dir=None: r'{source_path}'\n"
        "sys.modules['huggingface_hub'] = module\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "dataset.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + str(ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "examples.tool_selection.hf_dataset_exporter",
            "--dataset-id",
            "demo/dataset",
            "--repo-file",
            "BFCL_v3_simple.json",
            "--output",
            str(output_path),
            "--limit",
            "1",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    rows = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(rows) == 1
