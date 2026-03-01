"""Structured logging utilities with human-readable and JSON formatting.

This module provides custom formatters and centralized configuration
for structured logging to stderr while preserving print() output to stdout.
"""

import json
import logging
import logging.config
import os
from datetime import datetime, timezone
from typing import Any


class HumanReadableFormatter(logging.Formatter):
    """Human-readable log formatter with context."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as human-readable text.

        Format: YYYY-MM-DD HH:MM:SS.mmm [LEVEL] logger.name - message (key=value, ...)
        """
        # Format timestamp
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # milliseconds

        # Build base message
        parts = [
            timestamp,
            f"[{record.levelname}]",
            record.name,
            "-",
            record.getMessage(),
        ]

        # Add extra context if present
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields and isinstance(extra_fields, dict):
            context_parts = [f"{k}={v}" for k, v in extra_fields.items()]
            parts.append(f"({', '.join(context_parts)})")

        # Add exception info if present
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            return " ".join(parts) + "\n" + exception_text

        return " ".join(parts)


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields and isinstance(extra_fields, dict):
            log_data.update(extra_fields)

        return json.dumps(log_data)


def configure_logging() -> None:
    """Configure logging using dictConfig.

    Reads environment variables:
    - KALSHI_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR) - Default: INFO
    - KALSHI_LOG_FORMAT: Format ("human" or "json") - Default: human

    This function should be called once at application startup.
    """
    # Get configuration from environment
    log_level = os.environ.get("KALSHI_LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("KALSHI_LOG_FORMAT", "human").lower()

    # Validate log level
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        log_level = "INFO"

    # Validate log format
    if log_format not in ("human", "json"):
        log_format = "human"

    # Configure logging using dictConfig
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "human": {
                "()": "kalshi_lp.logging_utils.HumanReadableFormatter",
            },
            "json": {
                "()": "kalshi_lp.logging_utils.JSONFormatter",
            },
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": log_format,
            },
        },
        "loggers": {
            "kalshi_lp": {
                "level": log_level,
                "handlers": ["stderr"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get or create logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Note:
        configure_logging() must be called before using this function.
    """
    return logging.getLogger(name)


def log_api_call(
    logger: logging.Logger, method: str, endpoint: str, **kwargs: Any
) -> None:
    """Log API call with structured context.

    Args:
        logger: Logger instance
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint
        **kwargs: Additional context (ticker, status, etc.)
    """
    extra_fields = {"method": method, "endpoint": endpoint, **kwargs}
    logger.info(
        f"API call: {method} {endpoint}",
        extra={"extra_fields": extra_fields},
    )


def log_analysis_start(logger: logging.Logger, ticker: str, analysis_type: str) -> None:
    """Log start of market analysis.

    Args:
        logger: Logger instance
        ticker: Market ticker
        analysis_type: Type of analysis (full, debug, onesided, etc.)
    """
    logger.info(
        f"Starting {analysis_type} analysis for {ticker}",
        extra={"extra_fields": {"ticker": ticker, "analysis_type": analysis_type}},
    )


def log_analysis_complete(
    logger: logging.Logger,
    ticker: str,
    analysis_type: str,
    duration_ms: float,
) -> None:
    """Log completion of market analysis.

    Args:
        logger: Logger instance
        ticker: Market ticker
        analysis_type: Type of analysis
        duration_ms: Duration in milliseconds
    """
    logger.info(
        f"Completed {analysis_type} analysis for {ticker}",
        extra={
            "extra_fields": {
                "ticker": ticker,
                "analysis_type": analysis_type,
                "duration_ms": duration_ms,
            }
        },
    )


def log_error(
    logger: logging.Logger, error_type: str, message: str, **kwargs: Any
) -> None:
    """Log error with structured context.

    Args:
        logger: Logger instance
        error_type: Error category (api_error, validation_error, etc.)
        message: Error message
        **kwargs: Additional context
    """
    logger.error(
        message,
        extra={"extra_fields": {"error_type": error_type, **kwargs}},
    )
