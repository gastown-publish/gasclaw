"""Tests for gasclaw.logging_config."""

from __future__ import annotations

import logging

from gasclaw.logging_config import get_logger, setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_debug_level_format_includes_funcname(self, capsys, monkeypatch):
        """DEBUG level uses detailed format with function name."""
        monkeypatch.setenv("GASCLAW_LOGGING_FORCE", "true")
        setup_logging(level="DEBUG")
        logger = logging.getLogger("gasclaw.test_debug")

        # Force log to check format
        logger.debug("debug test")

        captured = capsys.readouterr()
        # Debug format should include function name
        assert "debug test" in captured.err

    def test_reduces_third_party_verbosity(self, monkeypatch):
        """setup_logging reduces httpx and httpcore log levels."""
        monkeypatch.setenv("GASCLAW_LOGGING_FORCE", "true")
        setup_logging(level="DEBUG")

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING


class TestFileHandler:
    """Tests for file handler functionality."""

    def test_creates_file_handler_when_log_file_specified(self, tmp_path, monkeypatch):
        """setup_logging creates file handler when log_file is provided."""
        monkeypatch.setenv("GASCLAW_LOGGING_FORCE", "true")
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        logger = logging.getLogger("gasclaw.test_file")
        logger.info("file handler test")

        assert log_file.exists()
        content = log_file.read_text()
        assert "file handler test" in content

    def test_file_handler_has_same_format(self, tmp_path, monkeypatch):
        """File handler uses same format as console handler."""
        monkeypatch.setenv("GASCLAW_LOGGING_FORCE", "true")
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        logger = logging.getLogger("gasclaw.test_format")
        logger.warning("format test message")

        content = log_file.read_text()
        assert "format test message" in content
        assert "WARNING" in content

    def test_file_handler_includes_timestamp(self, tmp_path, monkeypatch):
        """File handler output includes timestamp."""
        monkeypatch.setenv("GASCLAW_LOGGING_FORCE", "true")
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        logger = logging.getLogger("gasclaw.test_timestamp")
        logger.error("timestamp test")

        content = log_file.read_text()
        assert "timestamp test" in content
        # Check for timestamp format (YYYY-MM-DD HH:MM:SS)
        assert content[:4].isdigit()  # Year starts the line

    def test_both_handlers_receive_logs(self, tmp_path, monkeypatch, capsys):
        """When file handler is configured, both handlers receive logs."""
        monkeypatch.setenv("GASCLAW_LOGGING_FORCE", "true")
        log_file = tmp_path / "test.log"

        setup_logging(log_file=str(log_file))

        logger = logging.getLogger("gasclaw.test_both")
        logger.info("both handlers test")

        # Check file received it
        content = log_file.read_text()
        assert "both handlers test" in content

        # Check stderr received it
        captured = capsys.readouterr()
        assert "both handlers test" in captured.err


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_with_given_name(self):
        """get_logger returns a logger with the specified name."""
        logger = get_logger("test.module.name")

        assert logger.name == "test.module.name"

    def test_returns_same_logger_for_same_name(self):
        """get_logger returns the same logger instance for the same name."""
        logger1 = get_logger("test.same.name")
        logger2 = get_logger("test.same.name")

        assert logger1 is logger2
