"""Shared rich Console instance and progress bar factory.

All pipeline output goes through this console for consistent formatting.
Replaces tqdm with rich progress bars.
"""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

console = Console()


def create_progress(**kwargs) -> Progress:
    """Create a rich Progress bar with consistent styling.

    Accepts any keyword arguments that ``rich.progress.Progress`` accepts
    (e.g. ``transient=True``).
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        **kwargs,
    )
