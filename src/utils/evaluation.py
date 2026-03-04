"""Evaluation metric utilities for thaime-nlp research."""

from typing import Optional


def precision_at_k(
    candidates: list[str],
    expected: str,
    k: int = 1,
) -> float:
    """Check if the expected result appears in the top-k candidates.

    Args:
        candidates: Ordered list of candidate strings (best first).
        expected: The expected correct result.
        k: Number of top candidates to check.

    Returns:
        1.0 if expected is in top-k, 0.0 otherwise.
    """
    return 1.0 if expected in candidates[:k] else 0.0


def coverage(
    results: list[list[str]],
) -> float:
    """Calculate coverage: fraction of queries that returned any candidates.

    Args:
        results: List of candidate lists, one per query.

    Returns:
        Float between 0.0 and 1.0.
    """
    if not results:
        return 0.0
    return sum(1 for r in results if len(r) > 0) / len(results)


def mean_reciprocal_rank(
    results: list[tuple[list[str], str]],
) -> float:
    """Calculate Mean Reciprocal Rank (MRR).

    Args:
        results: List of (candidates, expected) tuples.

    Returns:
        MRR score between 0.0 and 1.0.
    """
    if not results:
        return 0.0

    total_rr = 0.0
    for candidates, expected in results:
        try:
            rank = candidates.index(expected) + 1
            total_rr += 1.0 / rank
        except ValueError:
            total_rr += 0.0  # Not found

    return total_rr / len(results)


def word_level_f1(
    predicted: list[str],
    expected: list[str],
) -> dict[str, float]:
    """Calculate word-level precision, recall, and F1 for segmentation.

    Args:
        predicted: List of predicted word segments.
        expected: List of expected word segments.

    Returns:
        Dict with keys 'precision', 'recall', 'f1'.
    """
    if not predicted and not expected:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted or not expected:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    predicted_set = set(predicted)
    expected_set = set(expected)

    true_positives = len(predicted_set & expected_set)

    precision = true_positives / len(predicted_set) if predicted_set else 0.0
    recall = true_positives / len(expected_set) if expected_set else 0.0

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {"precision": precision, "recall": recall, "f1": f1}
