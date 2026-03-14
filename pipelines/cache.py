"""Cache checking helper for pipeline intermediate files.

Logs which cached files are found (path + size) to help users
understand what will be reused vs regenerated.
"""

from __future__ import annotations

from pathlib import Path

from pipelines.console import console


def check_cache(path: Path, label: str | None = None) -> bool:
    """Check if a cached file exists and log it.

    Args:
        path: Path to the cached file.
        label: Human-readable label (defaults to filename).

    Returns:
        True if the file exists, False otherwise.
    """
    label = label or path.name
    if path.exists():
        size = path.stat().st_size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        console.print(f"  [green]cached[/green] {label} ({size_str})")
        return True
    else:
        console.print(f"  [dim]missing[/dim] {label}")
        return False
