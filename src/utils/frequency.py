"""Frequency normalization and merging utilities.

Shared across trie, n-gram, and benchmark pipelines for consistent
cross-corpus frequency handling.
"""

from __future__ import annotations

from collections import Counter


def normalize_frequencies(counter: Counter) -> dict[str, float]:
    """Normalize raw counts to a frequency distribution summing to 1.0."""
    total = sum(counter.values())
    if total == 0:
        return {}
    return {word: count / total for word, count in counter.items()}


def merge_frequencies(
    freq_dicts: list[dict[str, float]],
    weights: list[float] | None = None,
) -> dict[str, float]:
    """Merge frequency dicts with weighted averaging.

    Each source contributes according to its weight. Words absent from a
    source get 0 for that source's contribution.

    Args:
        freq_dicts: List of {word: normalized_freq} dicts.
        weights: Per-source weights. Default: equal weights (1/N each).

    Returns:
        Merged {word: weighted_avg_freq} dict.
    """
    if not freq_dicts:
        return {}

    if weights is None:
        weights = [1.0 / len(freq_dicts)] * len(freq_dicts)
    else:
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

    merged: dict[str, float] = {}
    all_words: set[str] = set()
    for fd in freq_dicts:
        all_words.update(fd.keys())

    for word in all_words:
        score = sum(fd.get(word, 0.0) * w for fd, w in zip(freq_dicts, weights))
        merged[word] = score

    return merged
