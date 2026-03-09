from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入範例模組：{module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_streamable_http_lab_examples_cover_handshake_modes_and_session_lifecycle():
    module = _load_module(
        REPO_ROOT / "examples" / "streamable_http" / "shared_demo.py",
        "streamable_http_shared_demo",
    )

    handshake = module.run_handshake_demo()
    assert handshake["initialize"]["status"] == 200
    assert handshake["initialize"]["session_id"]
    assert any(tool["name"] == "audio.vad.inspect_chunk" for tool in handshake["tools"])
    vad_tool = next(tool for tool in handshake["tools"] if tool["name"] == "audio.vad.inspect_chunk")
    assert vad_tool["input_schema"]["properties"]["avg_energy"]["type"] == "number"
    assert vad_tool["input_schema"]["properties"]["speech_band_ratio"]["type"] == "number"
    assert handshake["vad_result"]["route"] == "forward_to_asr"
    assert handshake["asr_result"]["accepted"] is True

    response_modes = module.run_response_mode_demo()
    assert response_modes["vad_gate"]["body"]["raw_result"]["route"] == "forward_to_asr"
    assert response_modes["json_mode"]["status"] == 200
    assert response_modes["stream_mode"]["status"] == 200
    assert response_modes["stream_mode"]["events"][0]["event"] == "message"
    assert response_modes["stream_mode"]["events"][1]["event"] == "done"

    lifecycle = module.run_session_resume_demo()
    assert lifecycle["ready_event"]["event"] == "ready"
    assert lifecycle["replay_after_last_event_id"] is None
    assert lifecycle["delete_result"]["body"]["session_closed"] is True
    assert lifecycle["after_delete"]["status"] == 404


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="torch 未安裝，跳過 PyTorch example smoke test",
)
def test_pytorch_model_example_runs() -> None:
    result = subprocess.run(
        [sys.executable, "examples/pytorch_tool.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    decisions = [item["prediction"]["speech_detected"] for item in payload["results"]]
    assert decisions == [False, False, True]
    assert payload["results"][2]["prediction"]["route"] == "forward_to_asr"


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("torch", "onnxruntime")),
    reason="torch 或 onnxruntime 未安裝，跳過 ONNX example smoke test",
)
def test_onnx_model_example_runs() -> None:
    result = subprocess.run(
        [sys.executable, "examples/onnx_tool.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    decisions = [item["prediction"]["speech_detected"] for item in payload["results"]]
    assert decisions == [False, False, True]
    assert payload["results"][2]["prediction"]["route"] == "forward_to_asr"
