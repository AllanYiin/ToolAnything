import logging
from pathlib import Path

logger = logging.getLogger("toolanything")


def configure_logging(log_dir: str = "logs") -> logging.Logger:
    """設定預設 logger，包含 console 與檔案輸出。"""

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_path / "toolanything.log", encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    logger.setLevel(logging.INFO)
    return logger


configure_logging()
