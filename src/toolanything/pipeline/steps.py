from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from toolanything.runtime.concurrency import ParallelOptions, RetryPolicy, parallel_run


class Step:
    async def run(self, manager, data: Any, *, context: Optional[Dict[str, Any]] = None) -> Any:
        raise NotImplementedError


@dataclass
class ToolStep(Step):
    tool_name: str
    args_builder: Optional[Callable[[Any, Optional[Dict[str, Any]]], Dict[str, Any]]] = None

    async def run(self, manager, data: Any, *, context: Optional[Dict[str, Any]] = None) -> Any:
        args = (
            self.args_builder(data, context)
            if self.args_builder
            else (data if isinstance(data, dict) else {"input": data})
        )
        return await manager.invoke(self.tool_name, args, context=context)


@dataclass
class ParallelStep(Step):
    steps: Mapping[str, Step]
    concurrency: int = 8
    max_retries: int = 0
    rate_limit_per_minute: Optional[int] = None

    async def run(self, manager, data: Any, *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        keys = list(self.steps.keys())
        step_list = [self.steps[k] for k in keys]

        policy = RetryPolicy(max_retries=self.max_retries)
        options = ParallelOptions(
            concurrency=min(self.concurrency, max(1, len(step_list))),
            preserve_order=True,
            retry_policy=policy,
            rate_limit_per_minute=self.rate_limit_per_minute,
        )

        factories = [(lambda s=s: s.run(manager, data, context=context)) for s in step_list]

        results = await parallel_run(factories, options=options)
        return {k: r for k, r in zip(keys, results)}
