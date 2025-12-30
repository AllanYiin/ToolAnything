"""ToolAnything 高階啟動 API。"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from toolanything.core.registry import ToolRegistry
from toolanything.server.mcp_stdio_server import run_stdio_server
from toolanything.server.mcp_tool_server import run_server
from toolanything.utils.logger import configure_logging, logger


def load_tool_module(module: str) -> None:
    """載入使用者工具模組，觸發 @tool 註冊。"""

    module_path = Path(module)
    if module_path.exists() and module_path.is_file():
        resolved = module_path.resolve()
        module_name = resolved.stem
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError(f"無法載入模組檔案：{resolved}")
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = loaded
        spec.loader.exec_module(loaded)
        return

    importlib.import_module(module)


def serve(
    *,
    module: str | None = None,
    host: str = "0.0.0.0",
    port: int = 9090,
    stdio: bool = False,
    registry: Optional[ToolRegistry] = None,
) -> None:
    """啟動 ToolAnything 伺服器。"""

    configure_logging()

    if module:
        load_tool_module(module)

    active_registry = registry or ToolRegistry.global_instance()

    if stdio:
        run_stdio_server(active_registry)
    else:
        run_server(port=port, host=host, registry=active_registry)


def run(
    *,
    module: str | None = None,
    host: str = "0.0.0.0",
    port: int = 9090,
    stdio: bool = False,
    registry: Optional[ToolRegistry] = None,
) -> None:
    """安全啟動入口，內建錯誤處理與 log。"""

    try:
        serve(module=module, host=host, port=port, stdio=stdio, registry=registry)
    except Exception:
        logger.exception("ToolAnything 伺服器啟動失敗")
        print("[ToolAnything] 伺服器啟動失敗，請查看 logs/toolanything.log")
