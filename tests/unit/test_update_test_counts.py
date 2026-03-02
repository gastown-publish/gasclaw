"""Tests for scripts/update_test_counts.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.update_test_counts import count_tests, main, update_file


class TestCountTests:
    """Tests for count_tests function."""

    def test_parses_collected_items_line(self):
        """Test parsing the standard pytest collect output."""
        mock_result = MagicMock()
        mock_result.stdout = "\n".join(
            [
                "test_module.py::test_one",
                "test_module.py::test_two",
                "",
                "========================== 2 items collected ==========================",
            ]
        )
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = count_tests("tests/unit")

        assert result == 2
        mock_run.assert_called_once_with(
            ["python", "-m", "pytest", "tests/unit", "--collect-only"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_parses_alternative_format(self):
        """Test parsing 'collected X items' format."""
        mock_result = MagicMock()
        mock_result.stdout = "collected 42 items\n\ntest_module.py::test_one"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = count_tests("tests/")

        assert result == 42

    def test_raises_on_subprocess_failure(self):
        """Test that subprocess errors are propagated."""
        error = subprocess.CalledProcessError(1, "pytest")
        error.stderr = "collection failed"

        with (
            patch("subprocess.run", side_effect=error),
            pytest.raises(subprocess.CalledProcessError),
        ):
            count_tests()

    def test_raises_when_pattern_not_found(self):
        """Test error when test count cannot be parsed."""
        mock_result = MagicMock()
        mock_result.stdout = "some unexpected output"
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="Could not parse test count"),
        ):
            count_tests()


class TestUpdateFile:
    """Tests for update_file function."""

    def test_updates_test_count(self, tmp_path: Path):
        """Test updating test count in a file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("This project has 100 tests.")

        result = update_file(test_file, 100, 150)

        assert result is True
        content = test_file.read_text()
        assert "150 tests" in content
        assert "100 tests" not in content

    def test_updates_unit_tests_phrase(self, tmp_path: Path):
        """Test updating 'unit tests' phrase."""
        test_file = tmp_path / "test.md"
        test_file.write_text("We have 200 unit tests in our suite.")

        result = update_file(test_file, 200, 250)

        assert result is True
        assert "250 unit tests" in test_file.read_text()

    def test_no_change_when_file_missing(self, tmp_path: Path):
        """Test handling of missing file."""
        missing_file = tmp_path / "nonexistent.md"

        result = update_file(missing_file, 100, 150)

        assert result is False

    def test_no_change_when_count_not_found(self, tmp_path: Path):
        """Test no modification when old count not present."""
        test_file = tmp_path / "test.md"
        test_file.write_text("This file has no test count.")

        result = update_file(test_file, 100, 150)

        assert result is False
        assert test_file.read_text() == "This file has no test count."

    def test_handles_multiple_occurrences(self, tmp_path: Path):
        """Test updating multiple occurrences of same count."""
        test_file = tmp_path / "test.md"
        test_file.write_text("We have 50 tests. Out of 50 tests, all pass.")

        result = update_file(test_file, 50, 75)

        assert result is True
        content = test_file.read_text()
        assert content.count("75 tests") == 2
        assert "50 tests" not in content

    def test_handles_case_insensitive_replacement(self, tmp_path: Path):
        """Test updating 'Tests' with capital T."""
        test_file = tmp_path / "test.md"
        test_file.write_text("This project has 100 Tests in total.")

        result = update_file(test_file, 100, 150)

        assert result is True
        assert "150 tests" in test_file.read_text()
        assert "100 Tests" not in test_file.read_text()

    def test_handles_singular_test(self, tmp_path: Path):
        """Test updating singular 'test' count."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Only 1 test exists.")

        result = update_file(test_file, 1, 2)

        assert result is True
        assert "2 tests" in test_file.read_text()

    def test_handles_from_to_pattern(self, tmp_path: Path):
        """Test updating 'from X to Y' pattern for PR descriptions."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Update test count from 100 to 200")

        result = update_file(test_file, 200, 250)

        assert result is True
        content = test_file.read_text()
        assert "from 100 to 250" in content


class TestMain:
    """Tests for main function."""

    def test_exits_zero_on_success(self):
        """Test successful execution returns 0."""
        with (
            patch("scripts.update_test_counts.count_tests", return_value=500),
            patch("scripts.update_test_counts.update_file", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="We have 485 tests"),
        ):
            result = main([])

        assert result == 0

    def test_exits_one_on_count_failure(self):
        """Test exit code 1 when test counting fails."""
        error = subprocess.CalledProcessError(1, "pytest")
        error.stderr = "error"

        with patch("scripts.update_test_counts.count_tests", side_effect=error):
            result = main([])

        assert result == 1

    def test_skips_update_when_count_unchanged(self):
        """Test no updates when test count hasn't changed."""
        with (
            patch("scripts.update_test_counts.count_tests", return_value=485),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="We have 485 tests"),
            patch("scripts.update_test_counts.update_file") as mock_update,
        ):
            result = main([])

        assert result == 0
        mock_update.assert_not_called()

    def test_accepts_custom_test_path(self):
        """Test --test-path argument is passed to count_tests."""
        with patch("scripts.update_test_counts.count_tests") as mock_count:
            mock_count.return_value = 100
            with patch("pathlib.Path.exists", return_value=False):
                main(["--test-path", "tests/integration"])

        mock_count.assert_called_once_with("tests/integration")

    def test_accepts_custom_files(self, tmp_path: Path):
        """Test specifying custom files to update."""
        custom_file = tmp_path / "custom.md"
        custom_file.write_text("This project has 10 tests.")

        with (
            patch("scripts.update_test_counts.count_tests", return_value=20),
            patch("scripts.update_test_counts.DEFAULT_FILES", []),
        ):
            result = main([str(custom_file)])

        assert result == 0
        assert "20 tests" in custom_file.read_text()

    def test_uses_old_count_from_argument(self):
        """Test --old-count argument bypasses auto-detection."""
        with (
            patch("scripts.update_test_counts.count_tests", return_value=200),
            patch("scripts.update_test_counts.update_file") as mock_update,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="We have 100 tests"),
        ):
            main(["--old-count", "150", "test.md"])

        mock_update.assert_called_once()
        args = mock_update.call_args
        assert args[0][1] == 150  # old_count
        assert args[0][2] == 200  # new_count


class TestMainEdgeCases:
    """Edge case tests for main function."""

    def test_handles_no_files_found(self):
        """Test behavior when no documentation files exist."""
        with (
            patch("scripts.update_test_counts.count_tests", return_value=100),
            patch("pathlib.Path.exists", return_value=False),
            patch("scripts.update_test_counts.update_file") as mock_update,
        ):
            result = main([])

        assert result == 0
        # update_file still gets called, but returns False for missing files
        assert mock_update.call_count == len(["README.md", "CLAUDE.md"])

    def test_falls_back_to_new_count_minus_one(self):
        """Test fallback when old count cannot be detected."""
        with (
            patch("scripts.update_test_counts.count_tests", return_value=100),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="No test count here"),
            patch("scripts.update_test_counts.update_file") as mock_update,
        ):
            main([])

        # Should fall back to new_count - 1 = 99
        mock_update.assert_called()
        args = mock_update.call_args
        assert args[0][1] == 99  # old_count = 100 - 1
