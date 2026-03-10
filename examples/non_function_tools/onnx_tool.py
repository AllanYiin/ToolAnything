from __future__ import annotations

import asyncio
import hashlib
import json
import math
from pathlib import Path

from toolanything import ModelHookRegistry, ModelSourceSpec, ToolManager


ASSET_PATH = Path(__file__).resolve().parent / "assets" / "tiny_vad_router.onnx"
ASSET_SHA256 = "fdad9f4b0ec9e2bb84721ab0253e1f8235f518e7bd7a5ac24e895f2c871da08d"
ASSET_SOURCE = (
    "手工建立的單層線性 VAD router，權重與 PyTorch 範例使用的 TinyVadRouter 相同。"
)


def _verify_asset(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"找不到 ONNX 範例模型：{path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ASSET_SHA256:
        raise RuntimeError(
            "ONNX 範例模型 checksum 不符，請重新執行 "
            "`python examples/non_function_tools/rebuild_tiny_vad_onnx.py`"
        )


def _decode_logits(payload):
    values = payload.get("logits", []) if isinstance(payload, dict) else payload
    silence_logit, speech_logit = [float(item) for item in values]
    odds = math.exp(speech_logit - silence_logit)
    speech_probability = odds / (1.0 + odds)
    speech_detected = speech_probability >= 0.5
    return {
        "speech_detected": speech_detected,
        "speech_probability": round(speech_probability, 4),
        "route": "forward_to_asr" if speech_detected else "skip_chunk",
        "explanation": (
            "偵測到連續語音活動，建議送往下一段 ASR/Whisper pipeline。"
            if speech_detected
            else "目前較像背景底噪或停頓，建議略過以節省後續推論成本。"
        ),
    }


async def _run_demo(manager: ToolManager) -> list[dict[str, object]]:
    scenarios = [
        {
            "case": "空調聲與鍵盤底噪",
            "vad_features": [0.08, 0.06, 0.05, 0.04, 0.88, 0.76],
        },
        {
            "case": "短暫停頓與呼吸聲",
            "vad_features": [0.18, 0.15, 0.12, 0.1, 0.52, 0.45],
        },
        {
            "case": "明顯人聲片段",
            "vad_features": [0.92, 0.84, 0.71, 0.66, 0.18, 0.12],
        },
    ]

    results: list[dict[str, object]] = []
    for scenario in scenarios:
        prediction = await manager.invoke("audio.vad.onnx", {"vad_features": scenario["vad_features"]})
        results.append(
            {
                "case": scenario["case"],
                "vad_features": scenario["vad_features"],
                "prediction": prediction,
            }
        )
    return results


def main() -> None:
    _verify_asset(ASSET_PATH)
    hooks = ModelHookRegistry()
    hooks.register("audio.decode_vad_logits", _decode_logits)

    manager = ToolManager()
    manager.register_model_tool(
        ModelSourceSpec(
            name="audio.vad.onnx",
            description="VAD 前置過濾示範（ONNX）",
            model_type="onnx",
            artifact_path=str(ASSET_PATH),
            input_spec={"vad_features": {"kind": "tensor", "dtype": "float32", "shape": [6]}},
            output_spec={
                "speech_detected": {"kind": "tensor", "dtype": "bool", "shape": []},
                "speech_probability": {"kind": "tensor", "dtype": "float32", "shape": []},
            },
            postprocessor_ref="audio.decode_vad_logits",
        ),
        hook_registry=hooks,
    )

    payload = {
        "example": "Voice activity detection gate (ONNX)",
        "artifact": str(ASSET_PATH),
        "artifact_sha256": ASSET_SHA256,
        "artifact_source": ASSET_SOURCE,
        "note": "這個範例直接使用 repo 內附的 tiny ONNX model，不再依賴 torch 匯出。",
        "results": asyncio.run(_run_demo(manager)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
