"""內建工具集合（僅供 doctor/diagnostic 注入）。"""
from __future__ import annotations

from typing import Any, Dict

from .registry import ToolRegistry
from ..decorators.tool import tool


PING_TOOL_NAME = "__ping__"


def register_ping_tool(registry: ToolRegistry) -> None:
    """註冊 __ping__ 工具，用於連線自檢。"""

    try:
        registry.get_tool(PING_TOOL_NAME)
        return
    except KeyError:
        pass

    @tool(
        name=PING_TOOL_NAME,
        description="連線診斷用 ping 工具，回傳固定結果",
        metadata={"side_effect": False, "cost": 0},
        registry=registry,
    )
    def _ping() -> Dict[str, Any]:
        return {"ok": True, "message": "pong"}
