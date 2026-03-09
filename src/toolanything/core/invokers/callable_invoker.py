"""以 Python callable 為來源的 compatibility invoker。"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Mapping

from ...pipeline.context import is_context_parameter
from ..runtime_types import ExecutionContext, InvocationResult, StreamEmitter


class CallableInvoker:
    """封裝現有 sync/async function 的執行語意。"""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func

    def _detect_context_argument(self) -> str | None:
        signature = inspect.signature(self.func)
        for name, param in signature.parameters.items():
            if is_context_parameter(param):
                return name
        return None

    async def _execute_callable(self, *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)

        result = await asyncio.to_thread(self.func, *args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def invoke(
        self,
        input: Mapping[str, Any] | None,
        context: ExecutionContext,
        stream: StreamEmitter | None = None,
        *,
        inject_context: bool = False,
        context_arg: str = "context",
    ) -> InvocationResult:
        del stream

        arguments = dict(input or {})
        context_param = context_arg if inject_context else self._detect_context_argument()

        if context_param and context_param not in arguments:
            arguments = {
                context_param: context.to_pipeline_context(),
                **arguments,
            }

        result = await self._execute_callable(**arguments)
        return InvocationResult(output=result)


__all__ = ["CallableInvoker"]
