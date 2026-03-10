from __future__ import annotations

import asyncio
import json
import math
import tempfile
from pathlib import Path

import torch

from toolanything import ModelHookRegistry, ModelSourceSpec, ToolManager


class TinyVadRouter(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.router = torch.nn.Linear(6, 2)
        with torch.no_grad():
            self.router.weight.copy_(
                torch.tensor(
                    [
                        [-1.35, -1.15, -0.8, -0.75, 0.95, 0.8],
                        [1.3, 1.05, 0.9, 0.7, -0.7, -0.55],
                    ],
                    dtype=torch.float32,
                )
            )
            self.router.bias.copy_(torch.tensor([1.25, -0.85], dtype=torch.float32))

    def forward(self, vad_features: torch.Tensor) -> torch.Tensor:
        return self.router(vad_features)


def _save_model(path: Path) -> Path:
    model = torch.jit.trace(TinyVadRouter().eval(), (torch.randn(6),))
    model.save(str(path))
    return path


def _decode_logits(payload):
    silence_logit, speech_logit = [float(item) for item in payload]
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
        prediction = await manager.invoke("audio.vad.pytorch", {"vad_features": scenario["vad_features"]})
        results.append(
            {
                "case": scenario["case"],
                "vad_features": scenario["vad_features"],
                "prediction": prediction,
            }
        )
    return results


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact = _save_model(Path(tmp_dir) / "tiny_vad_router.pt")
        hooks = ModelHookRegistry()
        hooks.register("audio.decode_vad_logits", _decode_logits)

        manager = ToolManager()
        manager.register_model_tool(
            ModelSourceSpec(
                name="audio.vad.pytorch",
                description="VAD 前置過濾示範（PyTorch）",
                model_type="pytorch",
                artifact_path=str(artifact),
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
            "example": "Voice activity detection gate (PyTorch)",
            "note": "這個範例把 PyTorch model tool 放在 ASR 前面，先做 VAD 門控，再決定要不要送去 Whisper 類流程。",
            "results": asyncio.run(_run_demo(manager)),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

