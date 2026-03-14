"""Utilities for resolving versioned data files."""

from __future__ import annotations

import re
from pathlib import Path

_SEMVER_RE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def resolve_latest_version(directory: Path, pattern: str) -> Path:
    """Find the latest semver-versioned file matching a glob pattern.

    Args:
        directory: Directory to search in.
        pattern: Glob pattern, e.g. "exclusions-v*.txt".

    Returns:
        Path to the file with the highest semantic version.

    Raises:
        FileNotFoundError: If no matching versioned files are found.
    """
    matches: list[tuple[tuple[int, int, int], Path]] = []
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        m = _SEMVER_RE.search(path.name)
        if m:
            version = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            matches.append((version, path))

    if not matches:
        raise FileNotFoundError(
            f"No versioned files matching '{pattern}' in {directory}"
        )

    matches.sort(key=lambda x: x[0])
    return matches[-1][1]
