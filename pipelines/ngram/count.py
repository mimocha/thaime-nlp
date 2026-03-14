"""N-gram counting from cached token files.

Reads token files produced by the tokenize stage, extracts sliding-window
n-grams, and outputs frequency tables as TSV.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path


def count_ngrams_from_file(
    token_path: Path,
    n: int,
    vocab: set[str] | None = None,
) -> Counter:
    """Count n-grams from a token file.

    Token files have one token per line, with blank lines as sequence
    boundaries. If vocab is provided, non-vocab tokens also act as
    sequence boundaries.
    """
    counter: Counter = Counter()
    window: list[str] = []

    with open(token_path, encoding="utf-8") as f:
        for line in f:
            token = line.strip()

            if not token:
                window.clear()
                continue

            if vocab is not None and token not in vocab:
                window.clear()
                continue

            window.append(token)
            if len(window) == n:
                counter[tuple(window)] += 1
                window.pop(0)

    return counter


def count_worker(args: tuple[Path, int, set[str] | None]) -> tuple[str, Counter]:
    """Worker function for parallel corpus counting."""
    token_path, n, vocab = args
    corpus_name = token_path.stem.removeprefix("tokens_")
    counter = count_ngrams_from_file(token_path, n, vocab)
    return corpus_name, counter


def save_ngrams_tsv(counter: Counter, path: Path, min_count: int) -> int:
    """Save n-gram counts to TSV, sorted by count descending.

    Returns the number of n-grams written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(path, "w", encoding="utf-8") as f:
        for ngram, count in counter.most_common():
            if count < min_count:
                break
            parts = "\t".join(ngram)
            f.write(f"{parts}\t{count}\n")
            written += 1
    return written


def normalize_and_merge(
    corpus_counters: dict[str, Counter],
) -> dict[tuple, float]:
    """Normalize each corpus to frequencies, then merge with equal weights.

    Each corpus is normalized to sum to 1.0, then all corpora contribute
    equally (weight = 1/N) to the merged frequency.
    """
    n_corpora = len(corpus_counters)
    weight = 1.0 / n_corpora

    merged: dict[tuple, float] = {}
    for name, counter in corpus_counters.items():
        total = sum(counter.values())
        if total == 0:
            continue
        for ngram, count in counter.items():
            merged[ngram] = merged.get(ngram, 0.0) + (count / total) * weight

    return merged


def save_ngrams_freq_tsv(
    freq_dict: dict[tuple, float],
    path: Path,
    min_freq: float = 0.0,
) -> int:
    """Save normalized n-gram frequencies to TSV, sorted by frequency descending.

    Returns the number of n-grams written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_ngrams = sorted(freq_dict.items(), key=lambda x: x[1], reverse=True)
    written = 0
    with open(path, "w", encoding="utf-8") as f:
        for ngram, freq in sorted_ngrams:
            if freq < min_freq:
                break
            parts = "\t".join(ngram)
            f.write(f"{parts}\t{freq:.12e}\n")
            written += 1
    return written
