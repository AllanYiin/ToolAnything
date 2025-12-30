from .context import PipelineContext

__all__ = ["PipelineContext", "ParallelStep", "Step", "ToolStep"]


def __getattr__(name: str):
    if name in {"ParallelStep", "Step", "ToolStep"}:
        from .steps import ParallelStep, Step, ToolStep

        return {"ParallelStep": ParallelStep, "Step": Step, "ToolStep": ToolStep}[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
