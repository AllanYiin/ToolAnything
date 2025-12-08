class ToolAnythingError(Exception):
    """ToolAnything 的基礎例外。"""


class ToolNotFoundError(ToolAnythingError):
    """註冊表中找不到工具時拋出。"""


class SchemaValidationError(ToolAnythingError):
    """參數驗證失敗時拋出。"""
