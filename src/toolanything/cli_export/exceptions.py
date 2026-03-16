"""CLI export 專用例外。"""
from __future__ import annotations


class CLIExportError(Exception):
    """CLI export 基底例外。"""


class CLIProjectConfigError(CLIExportError):
    """CLI project config 讀寫或驗證失敗。"""


class CLINamingConflictError(CLIExportError):
    """命名或 alias 衝突。"""


class CLIArgumentValidationError(CLIExportError):
    """CLI 參數驗證失敗。"""


class CLIOutputSerializationError(CLIExportError):
    """CLI JSON 序列化失敗。"""


class CLIUnsupportedFeatureError(CLIExportError):
    """尚未支援的功能。"""
