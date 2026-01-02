from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["PipelineContext", "ParallelStep", "Step", "ToolStep"]

if TYPE_CHECKING:
    from .context import PipelineContext
    from .steps import ParallelStep, Step, ToolStep


def __getattr__(name: str):
    if name == "PipelineContext":
        from .context import PipelineContext

        return PipelineContext
    if name in {"ParallelStep", "Step", "ToolStep"}:
        from .steps import ParallelStep, Step, ToolStep

        return {"ParallelStep": ParallelStep, "Step": Step, "ToolStep": ToolStep}[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
