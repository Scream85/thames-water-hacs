"""Structured logging configuration."""

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from src.config import get_settings


class StructuredFormatter(logging.Formatter):
    """JSON-like structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured output."""
        timestamp = datetime.now(timezone.utc).isoformat()

        log_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Format as structured string (not full JSON to keep readable)
        parts = [f"{timestamp} [{record.levelname:>8}] {record.name}: {record.getMessage()}"]

        # Add extra context
        extra_keys = [k for k in record.__dict__ if k not in {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "exc_info", "exc_text",
            "thread", "threadName", "message", "extra"
        }]

        if extra_keys:
            extra_parts = [f"{k}={getattr(record, k)}" for k in extra_keys]
            parts.append(f"  context: {', '.join(extra_parts)}")

        return "\n".join(parts)


def setup_logging() -> None:
    """Configure application logging."""
    settings = get_settings()

    # Get log level
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    log_level = level_map.get(settings.log_level, logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds context to all log messages."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process log message and add extra context."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_contextual_logger(name: str, **context: Any) -> LoggerAdapter:
    """Get a logger with additional context attached to all messages."""
    logger = get_logger(name)
    return LoggerAdapter(logger, context)
