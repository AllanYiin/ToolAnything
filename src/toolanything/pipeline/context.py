"""Pipeline 執行時的上下文。"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Optional

from toolanything.state.manager import StateManager


class PipelineContext:
    def __init__(self, state_manager: Optional[StateManager], user_id: Optional[str]):
        self.state_manager = state_manager
        self.user_id = user_id or "anonymous"

    @classmethod
    def matches_parameter(cls, parameter: inspect.Parameter) -> bool:
        """判斷函數參數是否應注入 PipelineContext。

        目前同時支援名稱為 ``ctx`` 的慣用命名，或型別標註為
        :class:`PipelineContext`（含子類別）的參數，方便工具/pipeline 在需要
        狀態時自行定義參數名稱。
        """

        if parameter.name == "ctx":
            return True

        annotation = parameter.annotation
        if annotation is inspect._empty:
            return False

        try:
            return issubclass(annotation, cls)
        except TypeError:
            return False

    def _resolve_awaitable(self, maybe_awaitable: Any, *, op: str) -> Any:
        """在同步情境下將 awaitable 轉為結果，避免直接回傳 coroutine。"""

        if not inspect.isawaitable(maybe_awaitable):
            return maybe_awaitable

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 沒有執行中的事件迴圈，直接同步執行
            return asyncio.run(maybe_awaitable)

        # 已有事件迴圈時無法同步等待，提示改用 async 介面
        raise RuntimeError(
            f"Detected async state operation during '{op}'. "
            "Use the async variants (aget/aset) inside async pipelines."
        )

    def get(self, key: str, default: Any = None) -> Any:
        if self.state_manager is None:
            return default

        bucket = self._resolve_awaitable(self.state_manager.get(self.user_id), op="get")
        return bucket.get(key, default)

    async def aget(self, key: str, default: Any = None) -> Any:
        if self.state_manager is None:
            return default

        bucket = self.state_manager.get(self.user_id)
        if inspect.isawaitable(bucket):
            bucket = await bucket
        return bucket.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self.state_manager is None:
            return

        self._resolve_awaitable(self.state_manager.set(self.user_id, key, value), op="set")

    async def aset(self, key: str, value: Any) -> None:
        if self.state_manager is None:
            return

        result = self.state_manager.set(self.user_id, key, value)
        if inspect.isawaitable(result):
            await result
