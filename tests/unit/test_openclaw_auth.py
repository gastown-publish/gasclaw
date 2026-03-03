"""Tests for gasclaw.openclaw.auth."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

from gasclaw.openclaw.auth import get_gateway_auth_token


class TestGetGatewayAuthToken:
    """Test get_gateway_auth_token function."""

    def test_returns_token_from_config(self, tmp_path):
        """Test successfully reading token from config file."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({
            "gateway": {"auth": {"token": "test-token-123"}}
        }))

        token = get_gateway_auth_token(tmp_path)
        assert token == "test-token-123"

    def test_returns_empty_when_no_token(self, tmp_path, caplog):
        """Test empty token when gateway.auth.token is missing."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({
            "gateway": {"auth": {}}
        }))

        with caplog.at_level(logging.WARNING):
            token = get_gateway_auth_token(tmp_path)

        assert token == ""
        assert "No auth token found" in caplog.text

    def test_returns_empty_when_no_gateway(self, tmp_path, caplog):
        """Test empty token when gateway section is missing."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({"other": "config"}))

        with caplog.at_level(logging.WARNING):
            token = get_gateway_auth_token(tmp_path)

        assert token == ""
        assert "No auth token found" in caplog.text

    def test_returns_empty_when_no_auth(self, tmp_path, caplog):
        """Test empty token when auth section is missing."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({"gateway": {}}))

        with caplog.at_level(logging.WARNING):
            token = get_gateway_auth_token(tmp_path)

        assert token == ""
        assert "No auth token found" in caplog.text

    def test_file_not_exists_logs_warning(self, tmp_path, caplog):
        """Test warning logged when config file doesn't exist."""
        non_existent_dir = tmp_path / "nonexistent"

        with caplog.at_level(logging.WARNING):
            token = get_gateway_auth_token(non_existent_dir)

        assert token == ""
        assert "openclaw.json not found" in caplog.text

    def test_invalid_json_logs_error(self, tmp_path, caplog):
        """Test error logged when JSON is invalid."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text("not valid json {[")

        with caplog.at_level(logging.ERROR):
            token = get_gateway_auth_token(tmp_path)

        assert token == ""
        assert "Invalid JSON" in caplog.text

    def test_oserror_logs_error(self, tmp_path, caplog):
        """Test error logged when file read fails with OSError."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({
            "gateway": {"auth": {"token": "test"}}
        }))

        with caplog.at_level(logging.ERROR), patch.object(
            Path, "read_text", side_effect=OSError("Permission denied")
        ):
            token = get_gateway_auth_token(tmp_path)

        assert token == ""
        assert "Error reading" in caplog.text

    def test_default_openclaw_dir(self, tmp_path, monkeypatch):
        """Test default directory is ~/.openclaw when None passed."""
        # Create .openclaw directory and config file
        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_path = openclaw_dir / "openclaw.json"
        config_path.write_text(json.dumps({
            "gateway": {"auth": {"token": "home-token"}}
        }))

        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        token = get_gateway_auth_token(None)
        assert token == "home-token"

    def test_logs_debug_on_success(self, tmp_path, caplog):
        """Test debug log on successful token read."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text(json.dumps({
            "gateway": {"auth": {"token": "my-token"}}
        }))

        with caplog.at_level(logging.DEBUG):
            get_gateway_auth_token(tmp_path)

        assert "Read auth token from" in caplog.text
