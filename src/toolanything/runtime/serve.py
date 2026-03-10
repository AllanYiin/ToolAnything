"""ToolAnything 高階啟動 API。"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from ..core.registry import ToolRegistry
from ..server.mcp_stdio_server import run_stdio_server
from ..server.mcp_streamable_http import run_server as run_streamable_http_server
from ..server.mcp_tool_server import run_server as run_legacy_http_server
from ..utils.logger import configure_logging, logger

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _looks_like_file_path(module: str) -> bool:
    return module.endswith(".py") or "/" in module or "\\" in module


def _resolve_tool_module_path(module: str) -> Path | None:
    module_path = Path(module)
    candidates: list[Path] = []
    if module_path.is_absolute():
        candidates.append(module_path)
    else:
        candidates.append(Path.cwd() / module_path)
        candidates.append(_REPO_ROOT / module_path)

    seen: set[Path] = set()
    for candidate in candidates:
        normalized = candidate.resolve(strict=False)
        if normalized in seen:
            continue
        seen.add(normalized)
        if normalized.exists() and normalized.is_file():
            return normalized
    return None


def load_tool_module(module: str) -> None:
    """載入使用者工具模組，觸發 @tool 註冊。"""

    resolved = _resolve_tool_module_path(module)
    if resolved is not None:
        module_name = resolved.stem
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError(f"無法載入模組檔案：{resolved}")
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = loaded
        spec.loader.exec_module(loaded)
        return

    if _looks_like_file_path(module):
        raise FileNotFoundError(
            f"找不到工具模組檔案：{module}。"
            f" 目前工作目錄：{Path.cwd()}。"
            f" 請改用絕對路徑，或切到 repo root：{_REPO_ROOT}"
        )

    importlib.import_module(module)


def serve(
    *,
    module: str | None = None,
    host: str = "127.0.0.1",
    port: int = 9090,
    stdio: bool = False,
    streamable_http: bool = False,
    registry: Optional[ToolRegistry] = None,
) -> None:
    """啟動 ToolAnything 伺服器。"""

    configure_logging()

    if module:
        load_tool_module(module)

    active_registry = registry or ToolRegistry.global_instance()

    if stdio:
        run_stdio_server(active_registry)
    elif streamable_http:
        run_streamable_http_server(port=port, host=host, registry=active_registry)
    else:
        run_legacy_http_server(port=port, host=host, registry=active_registry)


def run(
    *,
    module: str | None = None,
    host: str = "127.0.0.1",
    port: int = 9090,
    stdio: bool = False,
    streamable_http: bool = False,
    registry: Optional[ToolRegistry] = None,
) -> None:
    """安全啟動入口，內建錯誤處理與 log。"""

    try:
        serve(
            module=module,
            host=host,
            port=port,
            stdio=stdio,
            streamable_http=streamable_http,
            registry=registry,
        )
    except Exception:
        logger.exception("ToolAnything 伺服器啟動失敗")
        print("[ToolAnything] 伺服器啟動失敗，請查看 logs/toolanything.log")
