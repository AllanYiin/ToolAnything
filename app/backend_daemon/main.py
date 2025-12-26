from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI

from app.backend_daemon.logging_utils import get_logger

LOG_DIR = Path(os.getenv("BACKEND_DAEMON_LOG_DIR", "logs"))
logger = get_logger("backend_daemon.launcher", LOG_DIR, "backend_daemon_launcher.log")
PID_FILE = LOG_DIR / "backend_daemon.pid"

app = FastAPI(title="Backend Daemon API")


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        content = PID_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        logger.exception("讀取 PID 檔案失敗")
        return None
    if not content:
        return None
    try:
        return int(content)
    except ValueError:
        logger.warning("PID 檔案內容異常，將重新啟動 worker")
        return None


def _write_pid(pid: int) -> None:
    try:
        PID_FILE.write_text(str(pid), encoding="utf-8")
    except Exception:
        logger.exception("寫入 PID 檔案失敗")


def _should_auto_start() -> bool:
    value = os.getenv("BACKEND_DAEMON_AUTO_START", "true").lower()
    return value not in {"0", "false", "no"}


def _start_worker_process() -> None:
    if not _should_auto_start():
        logger.info("BACKEND_DAEMON_AUTO_START 已關閉，略過 worker 啟動")
        return

    existing_pid = _read_pid()
    if existing_pid and _is_process_running(existing_pid):
        logger.info("Backend daemon worker 已在執行中 (pid=%s)", existing_pid)
        return

    if existing_pid and not _is_process_running(existing_pid):
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            logger.exception("清理舊 PID 檔案失敗")

    cmd = [sys.executable, "-m", "app.backend_daemon.worker"]
    kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }

    if os.name == "nt":
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen(cmd, **kwargs)
        _write_pid(process.pid)
        logger.info("Backend daemon worker 已啟動 (pid=%s)", process.pid)
    except Exception:
        logger.exception("Backend daemon worker 啟動失敗")


@app.on_event("startup")
async def startup_event() -> None:
    _start_worker_process()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
