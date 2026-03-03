#!/usr/bin/env python3
"""Update test counts in documentation files.

This script runs the test suite, counts the tests, and updates
all references in documentation files (README.md, CLAUDE.md, etc.).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_FILES = ["README.md", "CLAUDE.md"]


def count_tests(test_path: str = "tests/unit") -> int:
    """Run pytest in collect-only mode and count tests.

    Args:
        test_path: Path to test directory or file.

    Returns:
        Number of tests found.

    Raises:
        subprocess.CalledProcessError: If pytest fails.
    """
    result = subprocess.run(
        ["python", "-m", "pytest", test_path, "--collect-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Look for "collected X items" or "X items collected" in output
    match = re.search(r"(\d+)\s+items?\s+collected|collected\s+(\d+)\s+items?", result.stdout)
    if match:
        # One of the groups will have the number
        return int(match.group(1) or match.group(2))
    raise RuntimeError(f"Could not parse test count from output: {result.stdout[:500]}")


def update_file(filepath: Path, old_count: int, new_count: int) -> bool:
    """Update test count references in a file.

    Args:
        filepath: Path to the file to update.
        old_count: The old test count to replace.
        new_count: The new test count.

    Returns:
        True if file was modified, False otherwise.
    """
    if not filepath.exists():
        return False

    content = filepath.read_text()
    original = content

    # Replace various formats of test count references
    patterns = [
        # "485 tests" -> "486 tests"
        (rf"\b{old_count}\s+tests?\b", f"{new_count} tests"),
        # "485 unit tests" -> "486 unit tests"
        (rf"\b{old_count}\s+unit\s+tests?\b", f"{new_count} unit tests"),
        # "from 484 to 485" -> "from 484 to 486" (for PR descriptions)
        (rf"from\s+(\d+)\s+to\s+{old_count}\b", rf"from \1 to {new_count}"),
        # "test count from 484 to 485" pattern
        (
            rf"test count from {old_count} to {new_count}",
            f"test count from {old_count} to {new_count}",
        ),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

    if content != original:
        filepath.write_text(content)
        return True
    return False


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        args: Command line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(description="Update test counts in documentation files")
    parser.add_argument(
        "--test-path",
        default="tests/unit",
        help="Path to tests (default: tests/unit)",
    )
    parser.add_argument(
        "--old-count",
        type=int,
        help="Old test count (auto-detected if not provided)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help=f"Files to update (default: {' '.join(DEFAULT_FILES)})",
    )
    parsed = parser.parse_args(args)

    files = parsed.files or DEFAULT_FILES

    try:
        new_count = count_tests(parsed.test_path)
        print(f"Found {new_count} tests")
    except subprocess.CalledProcessError as e:
        print(f"Failed to count tests: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Try to detect old count from first file
    old_count = parsed.old_count
    if old_count is None:
        for filename in files:
            filepath = Path(filename)
            if filepath.exists():
                content = filepath.read_text()
                # Look for patterns like "485 tests" or "485 unit tests"
                match = re.search(r"(\d+)\s+(?:unit\s+)?tests?\b", content, re.IGNORECASE)
                if match:
                    old_count = int(match.group(1))
                    print(f"Detected old count: {old_count} (from {filename})")
                    break

        if old_count is None:
            print("Could not detect old test count, using new_count - 1")
            old_count = new_count - 1

    if old_count == new_count:
        print(f"Test count is already up to date ({new_count})")
        return 0

    updated = []
    for filename in files:
        filepath = Path(filename)
        if update_file(filepath, old_count, new_count):
            print(f"Updated {filename}: {old_count} -> {new_count}")
            updated.append(filename)
        else:
            print(f"No changes needed in {filename}")

    if updated:
        print(f"\nUpdated test count in: {', '.join(updated)}")
    else:
        print("\nNo files were modified")

    return 0


if __name__ == "__main__":
    sys.exit(main())
