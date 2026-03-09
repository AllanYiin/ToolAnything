"""Model source invoker."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

from ...exceptions import ToolError
from ..model_runtime import ModelHookRegistry, ModelSessionCache
from ..runtime_types import ExecutionContext, InvocationResult, StreamEmitter
from ..source_specs import ModelSourceSpec


class ModelInvoker:
    """支援 PyTorch / ONNX 的模型推論 invoker。"""

    def __init__(
        self,
        source: ModelSourceSpec,
        *,
        session_cache: ModelSessionCache | None = None,
        hook_registry: ModelHookRegistry | None = None,
    ) -> None:
        self.source = source
        self.session_cache = session_cache or ModelSessionCache()
        self.hook_registry = hook_registry or ModelHookRegistry()

    def _artifact_path(self) -> str:
        path = self.source.artifact_path or self.source.model_ref
        if not path:
            raise ToolError(
                "缺少 model artifact_path 或 model_ref",
                error_type="model_artifact_not_found",
            )

        resolved = Path(path)
        if not resolved.exists():
            raise ToolError(
                f"找不到模型檔案: {path}",
                error_type="model_artifact_not_found",
                data={"artifact_path": str(path)},
            )
        return str(resolved)

    def _numpy_dtype(self, dtype_name: str):
        import numpy as np

        mapping = {
            "float32": np.float32,
            "float64": np.float64,
            "int32": np.int32,
            "int64": np.int64,
            "bool": np.bool_,
        }
        if dtype_name not in mapping:
            raise ToolError(
                f"不支援的 dtype: {dtype_name}",
                error_type="model_invalid_dtype",
                data={"dtype": dtype_name},
            )
        return mapping[dtype_name]

    def _validate_shape(self, name: str, array: Any, spec: Mapping[str, Any]) -> None:
        expected_shape = spec.get("shape")
        if not expected_shape:
            return

        actual_shape = list(getattr(array, "shape", ()))
        if len(actual_shape) != len(expected_shape):
            raise ToolError(
                f"{name} shape 不符",
                error_type="model_invalid_shape",
                data={"input": name, "expected": list(expected_shape), "actual": actual_shape},
            )

        for expected_dim, actual_dim in zip(expected_shape, actual_shape):
            if expected_dim in (None, -1):
                continue
            if expected_dim != actual_dim:
                raise ToolError(
                    f"{name} shape 不符",
                    error_type="model_invalid_shape",
                    data={"input": name, "expected": list(expected_shape), "actual": actual_shape},
                )

    def _prepare_inputs(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        import numpy as np

        prepared: dict[str, Any] = {}
        for name, spec in self.source.input_spec.items():
            if name not in payload:
                raise ToolError(
                    f"缺少必要 model 輸入: {name}",
                    error_type="validation_error",
                    data={"location": "model", "field": name},
                )

            dtype_name = str(spec.get("dtype", "float32"))
            value = payload[name]
            array = np.asarray(value, dtype=self._numpy_dtype(dtype_name))
            self._validate_shape(name, array, spec)
            prepared[name] = array
        return prepared

    def _serialize_output(self, output: Any) -> Any:
        import numpy as np

        try:
            import torch
        except Exception:
            torch = None  # type: ignore[assignment]

        if torch is not None and isinstance(output, torch.Tensor):
            return output.detach().cpu().numpy().tolist()
        if isinstance(output, np.ndarray):
            return output.tolist()
        if isinstance(output, (list, tuple)):
            return [self._serialize_output(item) for item in output]
        if isinstance(output, dict):
            return {key: self._serialize_output(value) for key, value in output.items()}
        return output

    def _load_pytorch_model(self, artifact_path: str):
        import torch

        def _loader():
            model = torch.jit.load(artifact_path, map_location=self.source.device)
            model.eval()
            return model

        return self.session_cache.get_or_load(
            ("pytorch", artifact_path, self.source.device),
            _loader,
        )

    def _run_pytorch(self, prepared_inputs: dict[str, Any]) -> Any:
        import torch

        artifact_path = self._artifact_path()
        model = self._load_pytorch_model(artifact_path)
        ordered_names = list(self.source.input_spec.keys())
        tensors = [
            torch.as_tensor(prepared_inputs[name], device=self.source.device)
            for name in ordered_names
        ]

        with torch.inference_mode():
            output = model(*tensors)
        return self._serialize_output(output)

    def _load_onnx_session(self, artifact_path: str):
        import onnxruntime as ort

        def _loader():
            providers = ["CPUExecutionProvider"]
            if self.source.device.lower().startswith("cuda"):
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            return ort.InferenceSession(artifact_path, providers=providers)

        return self.session_cache.get_or_load(
            ("onnx", artifact_path, self.source.device),
            _loader,
        )

    def _run_onnx(self, prepared_inputs: dict[str, Any]) -> Any:
        artifact_path = self._artifact_path()
        session = self._load_onnx_session(artifact_path)
        outputs = session.run(None, prepared_inputs)
        output_names = [output.name for output in session.get_outputs()]
        return {
            name: self._serialize_output(value)
            for name, value in zip(output_names, outputs)
        }

    def _apply_hook(self, ref: str | None, payload: Any) -> Any:
        hook = self.hook_registry.resolve(ref)
        if hook is None:
            return payload
        return hook(payload)

    def _run_model(self, payload: Mapping[str, Any]) -> Any:
        prepared_inputs = self._prepare_inputs(payload)
        if self.source.model_type == "pytorch":
            return self._run_pytorch(prepared_inputs)
        if self.source.model_type == "onnx":
            return self._run_onnx(prepared_inputs)

        raise ToolError(
            f"不支援的 model_type: {self.source.model_type}",
            error_type="model_runtime_failure",
            data={"model_type": self.source.model_type},
        )

    async def invoke(
        self,
        input: Mapping[str, Any] | None,
        context: ExecutionContext,
        stream: StreamEmitter | None = None,
        *,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> InvocationResult:
        del context, stream, inject_context, context_arg
        payload = self._apply_hook(self.source.preprocessor_ref, dict(input or {}))
        try:
            output = await asyncio.wait_for(
                asyncio.to_thread(self._run_model, payload),
                timeout=self.source.timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise ToolError(
                "模型推論逾時",
                error_type="model_timeout",
                data={"timeout_sec": self.source.timeout_sec},
            ) from exc
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                "模型推論失敗",
                error_type="model_runtime_failure",
                data={"message": str(exc)},
            ) from exc

        output = self._apply_hook(self.source.postprocessor_ref, output)
        return InvocationResult(output=output)


__all__ = ["ModelInvoker"]
