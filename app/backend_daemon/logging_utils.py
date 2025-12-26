from __future__ import annotations

import logging
from pathlib import Path


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, log_dir: Path, log_file: str) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if not logger.handlers:
        file_handler = logging.FileHandler(log_dir / log_file, encoding="utf-8")
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.setLevel(logging.INFO)
    return logger
