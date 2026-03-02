"""Centralized logging configuration for gasclaw.

Replaces print statements with proper structured logging.
Log level controlled via LOG_LEVEL env var (default: INFO).
"""

from __future__ import annotations

import logging
import os
import sys

# Default log format includes timestamp, level, and message
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEBUG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"

# Log level from env var, default to INFO
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


def setup_logging(level: str | None = None, log_file: str | None = None) -> None:
    """Configure root logging for gasclaw.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var.
        log_file: Optional file path to write logs to (in addition to stderr).
    """
    log_level = (level or LOG_LEVEL).upper()

    # Use more detailed format for DEBUG level
    fmt = DEBUG_FORMAT if log_level == "DEBUG" else DEFAULT_FORMAT
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    handlers: list[logging.Handler] = []

    # Console handler - always add
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger (allow override in tests via force parameter)
    force_config = os.environ.get("GASCLAW_LOGGING_FORCE", "true").lower() == "true"
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        handlers=handlers,
        force=force_config,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging configured with level={log_level}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Usually __name__ from the calling module.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
