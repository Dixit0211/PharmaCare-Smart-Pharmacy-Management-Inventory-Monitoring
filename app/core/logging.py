"""Application logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import settings


def setup_logging() -> None:
    """Configure root logger with stream and rotating file handlers."""
    settings.ensure_directories()
    log_file = Path(settings.LOG_FILE_PATH)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Base formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on multiple setup calls
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(numeric_level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    """Obtain a named logger instance with configured application defaults."""
    setup_logging()
    return logging.getLogger(name)
