"""Adapter 抽象基底，提供統一的 schema 與呼叫介面。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from toolanything.core.registry import ToolRegistry
from toolanything.core.failure_log import FailureLogManager


class BaseAdapter(ABC):
    """定義協議轉換器的共同介面。"""

    def __init__(
        self, registry: Optional[ToolRegistry] = None, *, failure_log: FailureLogManager | None = None
    ) -> None:
        # 預設使用全域 Registry，亦可注入自訂實例以便測試或隔離。
        self.registry = registry or ToolRegistry.global_instance()
        self.failure_log = failure_log

    @abstractmethod
    def to_schema(self) -> List[Dict[str, Any]]:
        """輸出符合特定協議的工具/流程列表。"""

    @abstractmethod
    async def to_invocation(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """執行工具並回傳符合協議的結果包裝。"""

