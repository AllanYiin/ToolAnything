from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import pytest
import torch

from toolanything.core import (
    ModelHookRegistry,
    ModelSessionCache,
    ModelSourceSpec,
    ToolManager,
    ToolRegistry,
    build_model_input_schema,
    register_model_tool,
)
from toolanything.exceptions import ToolError


class DoubleModule(torch.nn.Module):
    def forward(self, x):
        return x * 2


def _save_torchscript_model(path: Path) -> Path:
    model = torch.jit.trace(DoubleModule().eval(), (torch.randn(2),))
    model.save(str(path))
    return path


def _save_onnx_model(path: Path) -> Path:
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
        producer_name="toolanything-tests",
        opset_imports=[onnx.helper.make_opsetid("", 11)],
    )
    model.ir_version = 7
    onnx.save(model, path)
    return path


def _tensor_input_spec() -> dict[str, dict[str, object]]:
    return {
        "input": {
            "kind": "tensor",
            "dtype": "float32",
            "shape": [2],
        }
    }


def test_build_model_input_schema_for_tensor_spec():
    source = ModelSourceSpec(
        name="models.double",
        description="模型推論",
        model_type="pytorch",
        artifact_path="dummy.pt",
        input_spec=_tensor_input_spec(),
    )

    assert build_model_input_schema(source) == {
        "type": "object",
        "properties": {
            "input": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            }
        },
        "required": ["input"],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_register_model_tool_runs_pytorch_inference(tmp_path: Path):
    artifact = _save_torchscript_model(tmp_path / "double.pt")
    registry = ToolRegistry()
    register_model_tool(
        registry,
        ModelSourceSpec(
            name="models.double.pytorch",
            description="PyTorch double model",
            model_type="pytorch",
            artifact_path=str(artifact),
            input_spec=_tensor_input_spec(),
        ),
    )

    result = await registry.invoke_tool_async("models.double.pytorch", arguments={"input": [1.5, 2.5]})
    assert result == [3.0, 5.0]


@pytest.mark.asyncio
async def test_register_model_tool_runs_onnx_inference(tmp_path: Path):
    artifact = _save_onnx_model(tmp_path / "double.onnx")
    registry = ToolRegistry()
    register_model_tool(
        registry,
        ModelSourceSpec(
            name="models.double.onnx",
            description="ONNX double model",
            model_type="onnx",
            artifact_path=str(artifact),
            input_spec=_tensor_input_spec(),
        ),
    )

    result = await registry.invoke_tool_async("models.double.onnx", arguments={"input": [2.0, 4.0]})
    assert result == {"output": [4.0, 8.0]}


@pytest.mark.asyncio
async def test_model_tool_reports_invalid_shape(tmp_path: Path):
    artifact = _save_torchscript_model(tmp_path / "double.pt")
    registry = ToolRegistry()
    register_model_tool(
        registry,
        ModelSourceSpec(
            name="models.bad.shape",
            description="shape check",
            model_type="pytorch",
            artifact_path=str(artifact),
            input_spec=_tensor_input_spec(),
        ),
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async("models.bad.shape", arguments={"input": [1.0, 2.0, 3.0]})

    assert exc_info.value.to_dict()["type"] == "model_invalid_shape"


@pytest.mark.asyncio
async def test_model_tool_reports_missing_artifact():
    registry = ToolRegistry()
    register_model_tool(
        registry,
        ModelSourceSpec(
            name="models.missing.artifact",
            description="missing artifact",
            model_type="pytorch",
            artifact_path="does-not-exist.pt",
            input_spec=_tensor_input_spec(),
        ),
    )

    with pytest.raises(ToolError) as exc_info:
        await registry.invoke_tool_async("models.missing.artifact", arguments={"input": [1.0, 2.0]})

    assert exc_info.value.to_dict()["type"] == "model_artifact_not_found"


@pytest.mark.asyncio
async def test_model_tool_reuses_session_cache_for_pytorch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    artifact = _save_torchscript_model(tmp_path / "double.pt")
    registry = ToolRegistry()
    cache = ModelSessionCache()
    load_calls = {"count": 0}
    original_load = torch.jit.load

    def counting_load(*args, **kwargs):
        load_calls["count"] += 1
        return original_load(*args, **kwargs)

    monkeypatch.setattr(torch.jit, "load", counting_load)
    register_model_tool(
        registry,
        ModelSourceSpec(
            name="models.cache.pytorch",
            description="cache check",
            model_type="pytorch",
            artifact_path=str(artifact),
            input_spec=_tensor_input_spec(),
        ),
        session_cache=cache,
    )

    await registry.invoke_tool_async("models.cache.pytorch", arguments={"input": [1.0, 2.0]})
    await registry.invoke_tool_async("models.cache.pytorch", arguments={"input": [3.0, 4.0]})

    assert load_calls["count"] == 1


@pytest.mark.asyncio
async def test_model_tool_reuses_session_cache_for_onnx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    artifact = _save_onnx_model(tmp_path / "double.onnx")
    registry = ToolRegistry()
    cache = ModelSessionCache()
    load_calls = {"count": 0}
    original_session = ort.InferenceSession

    def counting_session(*args, **kwargs):
        load_calls["count"] += 1
        return original_session(*args, **kwargs)

    monkeypatch.setattr(ort, "InferenceSession", counting_session)
    register_model_tool(
        registry,
        ModelSourceSpec(
            name="models.cache.onnx",
            description="cache check",
            model_type="onnx",
            artifact_path=str(artifact),
            input_spec=_tensor_input_spec(),
        ),
        session_cache=cache,
    )

    await registry.invoke_tool_async("models.cache.onnx", arguments={"input": [1.0, 2.0]})
    await registry.invoke_tool_async("models.cache.onnx", arguments={"input": [3.0, 4.0]})

    assert load_calls["count"] == 1


@pytest.mark.asyncio
async def test_tool_manager_register_model_tool_supports_hooks(tmp_path: Path):
    artifact = _save_torchscript_model(tmp_path / "double.pt")
    manager = ToolManager(registry=ToolRegistry())
    hooks = ModelHookRegistry()
    hooks.register("pre:add_one", lambda payload: {"input": [value + 1 for value in payload["input"]]})
    hooks.register("post:sum", lambda output: {"sum": sum(output)})

    manager.register_model_tool(
        ModelSourceSpec(
            name="models.hooked",
            description="hooked model",
            model_type="pytorch",
            artifact_path=str(artifact),
            input_spec=_tensor_input_spec(),
            preprocessor_ref="pre:add_one",
            postprocessor_ref="post:sum",
        ),
        hook_registry=hooks,
    )

    result = await manager.invoke("models.hooked", {"input": [1.0, 2.0]})
    assert result == {"sum": 10.0}
