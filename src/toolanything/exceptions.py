from __future__ import annotations

from typing import Any, Dict


class ToolAnythingError(Exception):
    """ToolAnything 的基礎例外。"""


class ToolError(ToolAnythingError):
    """工具執行時可預期的錯誤，提供統一結構化資訊。"""

    def __init__(self, message: str, *, error_type: str = "tool_error", data: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.data: Dict[str, Any] = data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.error_type,
            "message": str(self),
            "data": self.data,
        }


class ToolNotFoundError(ToolAnythingError):
    """註冊表中找不到工具時拋出。"""


class SchemaValidationError(ToolAnythingError):
    """參數驗證失敗時拋出。"""


class RegistryError(ToolAnythingError):
    """註冊表相關錯誤"""


class AdapterError(ToolAnythingError):
    """適配器轉換錯誤"""
