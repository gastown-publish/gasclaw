"""Utility functions for atomic file operations.

Provides thread-safe and crash-safe file writing using atomic rename patterns.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["atomic_write", "atomic_write_json"]


def atomic_write(path: Path, content: str | bytes, *, mode: str = "w") -> None:
    """Write content to file atomically using rename pattern.

    Writes to a temporary file in the same directory, then renames atomically.
    This ensures that readers never see a partially-written file.

    Args:
        path: The target file path.
        content: Content to write (str or bytes).
        mode: File open mode ('w' for text, 'wb' for binary).

    Raises:
        OSError: If the write or rename fails.
        TypeError: If content type doesn't match mode.

    Example:
        >>> atomic_write(Path("/tmp/config.json"), '{"key": "value"}')
        >>> atomic_write(Path("/tmp/data.bin"), b"binary data", mode="wb")

    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (for atomic rename)
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, mode) as f:
            f.write(content)
        os.replace(temp_path, path)
    except (OSError, TypeError):
        # Clean up temp file on any failure
        with contextlib.suppress(OSError):
            os.unlink(temp_path)
        raise


def atomic_write_json(path: Path, data: dict[str, Any], *, indent: int | None = 2) -> None:
    """Write JSON data to file atomically.

    Args:
        path: The target file path.
        data: Dictionary to serialize as JSON.
        indent: Indentation level for pretty-printing (None for compact).

    Raises:
        OSError: If the write fails.
        TypeError: If data is not JSON serializable.

    Example:
        >>> atomic_write_json(Path("/tmp/state.json"), {"count": 42})

    """
    content = json.dumps(data, indent=indent)
    atomic_write(path, content, mode="w")
