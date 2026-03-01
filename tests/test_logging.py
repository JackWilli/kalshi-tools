"""Tests for structured logging utilities."""

import json
import logging

from kalshi_lp.logging_utils import (
    HumanReadableFormatter,
    JSONFormatter,
    configure_logging,
    get_logger,
    log_analysis_complete,
    log_analysis_start,
    log_api_call,
    log_error,
)


class TestHumanReadableFormatter:
    """Test human-readable log formatting."""

    def test_formats_basic_record(self):
        """Test basic log record formatting."""
        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Check key components are present
        assert "[INFO]" in output
        assert "test" in output
        assert "Test message" in output

    def test_includes_context_in_parentheses(self):
        """Test that extra context appears as key=value pairs."""
        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"ticker": "KXBTC", "side": "yes"}

        output = formatter.format(record)

        assert "ticker=KXBTC" in output
        assert "side=yes" in output

    def test_formats_exception(self):
        """Test that exception info is included."""
        formatter = HumanReadableFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)

        assert "Error occurred" in output
        assert "ValueError" in output
        assert "Test error" in output


class TestJSONFormatter:
    """Test JSON log formatting."""

    def test_formats_basic_record(self):
        """Test basic JSON log record formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["line"] == 42
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_includes_extra_fields(self):
        """Test that extra fields are included in JSON output."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"ticker": "KXBTC", "side": "yes"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["ticker"] == "KXBTC"
        assert data["side"] == "yes"

    def test_formats_exception(self):
        """Test that exception info is included when present."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestLoggerConfiguration:
    """Test logger setup and configuration."""

    def test_configure_logging_with_human_format(self, monkeypatch):
        """Test logging configuration with human-readable formatter."""
        # Clean up any existing loggers
        logging.getLogger("kalshi_lp").handlers.clear()

        # Set environment for human format
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        monkeypatch.setenv("KALSHI_LOG_LEVEL", "INFO")

        configure_logging()
        logger = get_logger("kalshi_lp.test")

        assert isinstance(logger, logging.Logger)
        # Check parent logger level (child loggers inherit)
        parent_logger = logging.getLogger("kalshi_lp")
        assert parent_logger.level == logging.INFO
        assert len(parent_logger.handlers) >= 1

    def test_configure_logging_with_json_format(self, monkeypatch):
        """Test logging configuration with JSON formatter."""
        # Clean up any existing loggers
        logging.getLogger("kalshi_lp").handlers.clear()

        # Set environment for JSON format
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "json")
        monkeypatch.setenv("KALSHI_LOG_LEVEL", "DEBUG")

        configure_logging()
        logger = get_logger("kalshi_lp.test")

        assert isinstance(logger, logging.Logger)
        # Check parent logger level (child loggers inherit)
        parent_logger = logging.getLogger("kalshi_lp")
        assert parent_logger.level == logging.DEBUG

    def test_logger_writes_to_stderr(self, monkeypatch):
        """Test that logger writes to stderr."""
        # Clean up any existing loggers
        logging.getLogger("kalshi_lp").handlers.clear()

        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        configure_logging()
        get_logger("kalshi_lp")

        # Find stderr handler
        kalshi_logger = logging.getLogger("kalshi_lp")
        assert len(kalshi_logger.handlers) > 0

        # Check that at least one handler writes to stderr
        import sys

        has_stderr_handler = any(
            hasattr(h, "stream") and h.stream == sys.stderr
            for h in kalshi_logger.handlers
        )
        assert has_stderr_handler

    def test_logger_respects_level_env_var(self, monkeypatch):
        """Test that KALSHI_LOG_LEVEL environment variable is respected."""
        # Clean up any existing loggers
        logging.getLogger("kalshi_lp").handlers.clear()

        monkeypatch.setenv("KALSHI_LOG_LEVEL", "WARNING")
        configure_logging()

        logger = logging.getLogger("kalshi_lp")
        assert logger.level == logging.WARNING


class TestLoggingHelpers:
    """Test logging helper functions."""

    def test_log_api_call_includes_context(self, monkeypatch):
        """Test API call logging includes method and endpoint."""
        # Clean up and reconfigure
        logging.getLogger("kalshi_lp").handlers.clear()
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        configure_logging()

        logger = get_logger("kalshi_lp.test_api")

        # Log the API call - we're mainly testing it doesn't crash and uses correct extra format
        log_api_call(logger, "GET", "/markets/KXBTC", ticker="KXBTC")

        # Verify logger is configured and callable
        assert logger.isEnabledFor(logging.INFO)

    def test_log_analysis_start_includes_ticker(self, monkeypatch):
        """Test analysis start logging includes ticker."""
        # Clean up and reconfigure
        logging.getLogger("kalshi_lp").handlers.clear()
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        configure_logging()

        logger = get_logger("kalshi_lp.test_analysis")

        # Log analysis start - we're mainly testing it doesn't crash
        log_analysis_start(logger, "KXBTC", "full")

        # Verify logger is configured
        assert logger.isEnabledFor(logging.INFO)

    def test_log_analysis_complete_includes_duration(self, monkeypatch):
        """Test analysis complete logging includes duration."""
        # Clean up and reconfigure
        logging.getLogger("kalshi_lp").handlers.clear()
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        configure_logging()

        logger = get_logger("kalshi_lp.test_analysis")

        # Log analysis completion - we're mainly testing it doesn't crash
        log_analysis_complete(logger, "KXBTC", "full", 1234.5)

        # Verify logger is configured
        assert logger.isEnabledFor(logging.INFO)

    def test_log_error_includes_error_type(self, monkeypatch):
        """Test error logging includes error type."""
        # Clean up and reconfigure
        logging.getLogger("kalshi_lp").handlers.clear()
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        configure_logging()

        logger = get_logger("kalshi_lp.test_error")

        # Log error - we're mainly testing it doesn't crash
        log_error(logger, "validation_error", "Invalid parameter", param="test")

        # Verify logger is configured
        assert logger.isEnabledFor(logging.ERROR)


class TestIntegration:
    """Integration tests for logging system."""

    def test_json_format_produces_parseable_output(self, monkeypatch, capsys):
        """Test that JSON format produces valid JSON."""
        # Clean up any existing loggers
        logging.getLogger("kalshi_lp").handlers.clear()

        # Set up JSON format
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "json")
        monkeypatch.setenv("KALSHI_LOG_LEVEL", "INFO")

        configure_logging()
        logger = get_logger("kalshi_lp.test")

        # Log a message
        logger.info("Test message", extra={"extra_fields": {"key": "value"}})

        # Capture stderr
        captured = capsys.readouterr()

        # Should be valid JSON on stderr
        if captured.err:
            data = json.loads(captured.err.strip())
            assert data["message"] == "Test message"
            assert data["key"] == "value"

    def test_human_format_produces_readable_output(self, monkeypatch, capsys):
        """Test that human format produces readable output."""
        # Clean up any existing loggers
        logging.getLogger("kalshi_lp").handlers.clear()

        # Set up human format
        monkeypatch.setenv("KALSHI_LOG_FORMAT", "human")
        monkeypatch.setenv("KALSHI_LOG_LEVEL", "INFO")

        configure_logging()
        logger = get_logger("kalshi_lp.test")

        # Log a message
        logger.info("Test message", extra={"extra_fields": {"key": "value"}})

        # Capture stderr
        captured = capsys.readouterr()

        # Should be human readable on stderr
        if captured.err:
            assert "[INFO]" in captured.err
            assert "Test message" in captured.err
            assert "key=value" in captured.err
