from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import torch

from toolanything import ModelSourceSpec, ToolManager


class DoubleModule(torch.nn.Module):
    def forward(self, x):
        return x * 2


def _save_model(path: Path) -> Path:
    model = torch.jit.trace(DoubleModule().eval(), (torch.randn(2),))
    model.save(str(path))
    return path


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact = _save_model(Path(tmp_dir) / "double.pt")
        manager = ToolManager()
        manager.register_model_tool(
            ModelSourceSpec(
                name="models.double.pytorch",
                description="示範 PyTorch model tool",
                model_type="pytorch",
                artifact_path=str(artifact),
                input_spec={"input": {"kind": "tensor", "dtype": "float32", "shape": [2]}},
            )
        )

        result = asyncio.run(manager.invoke("models.double.pytorch", {"input": [1.5, 2.5]}))
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
