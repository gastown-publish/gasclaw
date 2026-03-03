"""Tests for gasclaw.utils module."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from gasclaw.utils import atomic_write, atomic_write_json


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def test_write_text_file(self, tmp_path):
        """Can write text content to file."""
        target = tmp_path / "test.txt"
        atomic_write(target, "hello world")
        assert target.read_text() == "hello world"

    def test_write_binary_file(self, tmp_path):
        """Can write binary content to file."""
        target = tmp_path / "test.bin"
        atomic_write(target, b"binary data", mode="wb")
        assert target.read_bytes() == b"binary data"

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories if they don't exist."""
        target = tmp_path / "nested" / "deep" / "file.txt"
        atomic_write(target, "content")
        assert target.exists()
        assert target.read_text() == "content"

    def test_overwrites_existing_file(self, tmp_path):
        """Overwrites existing file atomically."""
        target = tmp_path / "existing.txt"
        target.write_text("old content")
        atomic_write(target, "new content")
        assert target.read_text() == "new content"

    def test_no_temp_files_left_behind(self, tmp_path):
        """Temporary files are cleaned up after successful write."""
        target = tmp_path / "clean.txt"
        atomic_write(target, "content")

        # Check no temp files remain
        temp_files = list(tmp_path.glob(".clean-*.tmp"))
        assert len(temp_files) == 0

    def test_cleans_up_temp_on_failure(self, tmp_path, monkeypatch):
        """Temp file is cleaned up if write fails."""
        target = tmp_path / "fail.txt"

        # Make os.fdopen fail
        def fail_fdopen(*args, **kwargs):
            raise OSError("Write failed")

        monkeypatch.setattr("os.fdopen", fail_fdopen)

        with pytest.raises(OSError, match="Write failed"):
            atomic_write(target, "content")

        # No temp files should remain
        temp_files = list(tmp_path.glob(".fail-*.tmp"))
        assert len(temp_files) == 0

    def test_preserves_file_permissions(self, tmp_path):
        """File permissions are preserved on overwrite."""
        target = tmp_path / "perms.txt"
        target.write_text("initial")
        # Set specific permissions
        target.chmod(0o600)

        atomic_write(target, "updated")

        # Check permissions preserved (may vary by umask)
        perms = stat.S_IMODE(target.stat().st_mode)
        assert perms == 0o600


class TestAtomicWriteJson:
    """Tests for atomic_write_json function."""

    def test_write_simple_dict(self, tmp_path):
        """Can write a simple dictionary as JSON."""
        target = tmp_path / "data.json"
        data = {"key": "value", "number": 42}
        atomic_write_json(target, data)

        assert target.exists()
        loaded = json.loads(target.read_text())
        assert loaded == data

    def test_pretty_print_by_default(self, tmp_path):
        """JSON is pretty-printed with indentation by default."""
        target = tmp_path / "pretty.json"
        data = {"a": 1, "b": 2}
        atomic_write_json(target, data)

        content = target.read_text()
        # Should contain newlines for pretty printing
        assert "\n" in content
        assert "  " in content  # Indentation

    def test_compact_json(self, tmp_path):
        """Can write compact JSON without indentation."""
        target = tmp_path / "compact.json"
        data = {"a": 1, "b": 2}
        atomic_write_json(target, data, indent=None)

        content = target.read_text()
        # Should be single line
        assert "\n" not in content.strip()

    def test_nested_data(self, tmp_path):
        """Can write nested dictionaries and lists."""
        target = tmp_path / "nested.json"
        data = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25},
            ],
            "metadata": {"version": 1.0, "active": True},
        }
        atomic_write_json(target, data)

        loaded = json.loads(target.read_text())
        assert loaded == data

    def test_special_characters(self, tmp_path):
        """Can handle special characters in strings."""
        target = tmp_path / "special.json"
        data = {
            "unicode": "Hello 世界 🌍",
            "quotes": 'He said "hello"',
            "newlines": "line1\nline2",
        }
        atomic_write_json(target, data)

        loaded = json.loads(target.read_text())
        assert loaded == data

    def test_empty_dict(self, tmp_path):
        """Can write empty dictionary."""
        target = tmp_path / "empty.json"
        atomic_write_json(target, {})

        loaded = json.loads(target.read_text())
        assert loaded == {}

    def test_rejects_non_serializable(self, tmp_path):
        """Raises TypeError for non-JSON-serializable data."""
        target = tmp_path / "invalid.json"

        class CustomClass:
            pass

        with pytest.raises(TypeError):
            atomic_write_json(target, {"obj": CustomClass()})

    def test_creates_directories(self, tmp_path):
        """Creates parent directories for JSON file."""
        target = tmp_path / "deep" / "path" / "config.json"
        atomic_write_json(target, {"key": "value"})
        assert target.exists()


class TestAtomicWriteEdgeCases:
    """Edge case tests for atomic write functions."""

    def test_empty_string_content(self, tmp_path):
        """Can write empty string."""
        target = tmp_path / "empty.txt"
        atomic_write(target, "")
        assert target.read_text() == ""

    def test_empty_bytes_content(self, tmp_path):
        """Can write empty bytes."""
        target = tmp_path / "empty.bin"
        atomic_write(target, b"", mode="wb")
        assert target.read_bytes() == b""

    def test_large_content(self, tmp_path):
        """Can write large content."""
        target = tmp_path / "large.txt"
        content = "x" * 1000000  # 1MB
        atomic_write(target, content)
        assert target.read_text() == content

    def test_filename_with_spaces(self, tmp_path):
        """Handles filenames with spaces."""
        target = tmp_path / "file with spaces.txt"
        atomic_write(target, "content")
        assert target.read_text() == "content"

    def test_unicode_filename(self, tmp_path):
        """Handles unicode filenames."""
        target = tmp_path / "文件 📝.txt"
        atomic_write(target, "content")
        assert target.read_text() == "content"
