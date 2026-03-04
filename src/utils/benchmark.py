"""Benchmark loading utilities for thaime-nlp research."""

import csv
from pathlib import Path
from typing import Optional

# Repo root is two levels up from this file
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARKS_DIR = REPO_ROOT / "benchmarks"


def load_benchmark(path: str | Path) -> list[dict]:
    """Load a benchmark CSV file and return a list of dicts.

    Args:
        path: Path to the CSV file (absolute or relative to repo root).

    Returns:
        List of dicts, one per row, with keys from the CSV header.
    """
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_word_conversion_benchmark(
    filename: str = "basic.csv",
) -> list[dict]:
    """Load the word conversion benchmark dataset.

    Args:
        filename: CSV file name within benchmarks/word-conversion/.

    Returns:
        List of dicts with keys: latin_input, expected_thai, category,
        difficulty, notes.
    """
    return load_benchmark(BENCHMARKS_DIR / "word-conversion" / filename)


def load_segmentation_benchmark(
    filename: str = "basic.csv",
) -> list[dict]:
    """Load the segmentation benchmark dataset.

    Args:
        filename: CSV file name within benchmarks/segmentation/.

    Returns:
        List of dicts with keys: latin_input, expected_segmentation,
        category, notes.
    """
    return load_benchmark(BENCHMARKS_DIR / "segmentation" / filename)


def load_ranking_benchmark(
    filename: str = "basic.csv",
) -> list[dict]:
    """Load the ranking benchmark dataset.

    Args:
        filename: CSV file name within benchmarks/ranking/.

    Returns:
        List of dicts with keys: latin_input, context, expected_top,
        valid_alternatives, notes.
    """
    return load_benchmark(BENCHMARKS_DIR / "ranking" / filename)


def filter_benchmark(
    data: list[dict],
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> list[dict]:
    """Filter benchmark entries by category and/or difficulty.

    Args:
        data: List of benchmark dicts (from a load function).
        category: Filter to this category (e.g., 'common', 'ambiguous').
        difficulty: Filter to this difficulty (e.g., 'easy', 'medium', 'hard').

    Returns:
        Filtered list of dicts.
    """
    result = data
    if category is not None:
        result = [row for row in result if row.get("category") == category]
    if difficulty is not None:
        result = [row for row in result if row.get("difficulty") == difficulty]
    return result
