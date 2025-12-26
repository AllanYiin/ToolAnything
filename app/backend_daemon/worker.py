from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable

from app.backend_daemon.logging_utils import get_logger


LOG_DIR = Path(os.getenv("BACKEND_DAEMON_LOG_DIR", "logs"))
logger = get_logger("backend_daemon.worker", LOG_DIR, "backend_daemon.log")


def _handle_shutdown(stop: Callable[[], None]) -> None:
    def _handler(signum: int, frame) -> None:
        logger.info("收到停止訊號 %s，準備結束 worker。", signum)
        stop()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


class _StopSignal:
    def __init__(self) -> None:
        self._stop = False

    def __call__(self) -> None:
        self._stop = True

    @property
    def triggered(self) -> bool:
        return self._stop


def run_worker() -> None:
    logger.info("Backend daemon worker 啟動。")
    stop_signal = _StopSignal()
    _handle_shutdown(stop_signal)

    while not stop_signal.triggered:
        try:
            time.sleep(1)
        except Exception:
            logger.exception("Backend daemon worker 發生未預期錯誤")
            time.sleep(1)

    logger.info("Backend daemon worker 結束。")


if __name__ == "__main__":
    try:
        run_worker()
    except Exception:
        logger.exception("Backend daemon worker 無法啟動")
        sys.exit(1)
