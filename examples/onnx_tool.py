from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import numpy as np
import onnx

from toolanything import ModelSourceSpec, ToolManager


def _save_model(path: Path) -> Path:
    input_tensor = onnx.helper.make_tensor_value_info("input", onnx.TensorProto.FLOAT, [2])
    output_tensor = onnx.helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [2])
    node = onnx.helper.make_node("Mul", ["input", "const_two"], ["output"])
    initializer = onnx.helper.make_tensor(
        "const_two",
        onnx.TensorProto.FLOAT,
        dims=[2],
        vals=np.array([2.0, 2.0], dtype=np.float32),
    )
    graph = onnx.helper.make_graph([node], "double_graph", [input_tensor], [output_tensor], [initializer])
    model = onnx.helper.make_model(
        graph,
        producer_name="toolanything-examples",
        opset_imports=[onnx.helper.make_opsetid("", 11)],
    )
    model.ir_version = 7
    onnx.save(model, path)
    return path


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact = _save_model(Path(tmp_dir) / "double.onnx")
        manager = ToolManager()
        manager.register_model_tool(
            ModelSourceSpec(
                name="models.double.onnx",
                description="示範 ONNX model tool",
                model_type="onnx",
                artifact_path=str(artifact),
                input_spec={"input": {"kind": "tensor", "dtype": "float32", "shape": [2]}},
            )
        )

        result = asyncio.run(manager.invoke("models.double.onnx", {"input": [2.0, 4.0]}))
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
