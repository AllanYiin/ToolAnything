from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import ml_dtypes


def _patch_ml_dtypes() -> None:
    fallbacks = {
        "float4_e2m1fn": ml_dtypes.float8_e4m3fn,
        "float8_e8m0fnu": ml_dtypes.float8_e4m3fn,
        "uint4": np.uint8,
        "int4": np.int8,
        "uint2": np.uint8,
        "int2": np.int8,
    }
    for name, value in fallbacks.items():
        if not hasattr(ml_dtypes, name):
            setattr(ml_dtypes, name, value)


_patch_ml_dtypes()

import onnx
from onnx import TensorProto, helper


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_PATH = REPO_ROOT / "examples" / "non_function_tools" / "assets" / "tiny_vad_router.onnx"

WEIGHTS = np.array(
    [
        [-1.35, 1.3],
        [-1.15, 1.05],
        [-0.8, 0.9],
        [-0.75, 0.7],
        [0.95, -0.7],
        [0.8, -0.55],
    ],
    dtype=np.float32,
)
BIAS = np.array([1.25, -0.85], dtype=np.float32)


def build_model() -> onnx.ModelProto:
    input_value = helper.make_tensor_value_info("vad_features", TensorProto.FLOAT, [6])
    output_value = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [2])

    weights = helper.make_tensor(
        name="linear_weight",
        data_type=TensorProto.FLOAT,
        dims=list(WEIGHTS.shape),
        vals=WEIGHTS.flatten().tolist(),
    )
    bias = helper.make_tensor(
        name="linear_bias",
        data_type=TensorProto.FLOAT,
        dims=list(BIAS.shape),
        vals=BIAS.flatten().tolist(),
    )

    nodes = [
        helper.make_node("MatMul", ["vad_features", "linear_weight"], ["matmul_out"]),
        helper.make_node("Add", ["matmul_out", "linear_bias"], ["logits"]),
    ]

    graph = helper.make_graph(
        nodes=nodes,
        name="TinyVadRouter",
        inputs=[input_value],
        outputs=[output_value],
        initializer=[weights, bias],
    )

    model = helper.make_model(
        graph,
        producer_name="toolanything",
        producer_version="1.0",
        opset_imports=[helper.make_opsetid("", 13)],
    )
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(build_model(), ASSET_PATH)
    print(f"wrote: {ASSET_PATH}")
    print(f"sha256: {sha256(ASSET_PATH)}")


if __name__ == "__main__":
    main()
