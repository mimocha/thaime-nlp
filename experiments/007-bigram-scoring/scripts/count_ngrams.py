"""Stage 2: Count n-grams from cached token files.

Reads token files produced by Stage 1, extracts sliding-window n-grams,
and outputs frequency tables as TSV.

Usage:
    python -m experiments.007-bigram-scoring.scripts.count_ngrams
    python -m experiments.007-bigram-scoring.scripts.count_ngrams --n 3
    python -m experiments.007-bigram-scoring.scripts.count_ngrams --min-count 5
    python -m experiments.007-bigram-scoring.scripts.count_ngrams --corpora wisesight,wongnai
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from .config import (
    CORPORA,
    OUTPUT_DIR,
    TRIE_DATASET_PATH,
)


def load_vocab(path: Path) -> set[str]:
    """Load vocabulary from trie dataset JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["thai"] for entry in data["entries"]}


def count_ngrams_from_file(
    token_path: Path,
    n: int,
    vocab: set[str] | None,
) -> Counter:
    """Count n-grams from a token file.

    Token files have one token per line, with blank lines as sequence
    boundaries. If vocab is provided, non-vocab tokens also act as
    sequence boundaries (for token files that weren't pre-filtered).
    """
    counter: Counter = Counter()
    window: list[str] = []

    with open(token_path, encoding="utf-8") as f:
        for line in f:
            token = line.strip()

            if not token:
                # Sequence boundary — flush window
                window.clear()
                continue

            # If vocab provided and token not in vocab, treat as boundary
            if vocab is not None and token not in vocab:
                window.clear()
                continue

            window.append(token)
            if len(window) == n:
                counter[tuple(window)] += 1
                window.pop(0)

    return counter


def _count_worker(args: tuple[Path, int, set[str] | None]) -> tuple[str, Counter]:
    """Worker function for parallel corpus counting."""
    token_path, n, vocab = args
    # Extract corpus name from filename: tokens_{name}.txt
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
    equally (weight = 1/N) to the merged frequency. This prevents large
    corpora from dominating smaller ones.

    Returns dict mapping n-gram tuple -> merged frequency.
    """
    n_corpora = len(corpus_counters)
    weight = 1.0 / n_corpora

    # Normalize each corpus
    corpus_freqs: list[dict[tuple, float]] = []
    for name, counter in corpus_counters.items():
        total = sum(counter.values())
        if total == 0:
            corpus_freqs.append({})
            continue
        freqs = {ngram: count / total for ngram, count in counter.items()}
        corpus_freqs.append(freqs)

    # Merge with equal weighting
    merged: dict[tuple, float] = {}
    for freqs in corpus_freqs:
        for ngram, freq in freqs.items():
            merged[ngram] = merged.get(ngram, 0.0) + freq * weight

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 2: Count n-grams from cached token files."
    )
    parser.add_argument(
        "--n",
        type=int,
        default=2,
        help="N-gram size (default: 2)",
    )
    parser.add_argument(
        "--corpora",
        type=str,
        default=",".join(CORPORA),
        help=f"Comma-separated corpus names (default: {','.join(CORPORA)})",
    )
    parser.add_argument(
        "--vocab-path",
        type=str,
        default=str(TRIE_DATASET_PATH),
        help=f"Path to trie dataset JSON for vocab filtering (default: {TRIE_DATASET_PATH})",
    )
    parser.add_argument(
        "--no-vocab-filter",
        action="store_true",
        help="Skip vocabulary filtering (use only if token files were pre-filtered)",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum n-gram count to include in output (default: 2)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help=f"Input directory with token files (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory for n-gram TSVs (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    corpora = [c.strip() for c in args.corpora.split(",")]
    input_dir = Path(args.input_dir) if args.input_dir else OUTPUT_DIR
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Verify token files exist
    token_paths: list[Path] = []
    for corpus_name in corpora:
        token_path = input_dir / f"tokens_{corpus_name}.txt"
        if not token_path.exists():
            print(f"ERROR: Token file not found: {token_path}")
            print("  Run tokenize_corpora.py first (Stage 1).")
            sys.exit(1)
        token_paths.append(token_path)

    # Load vocab for filtering (unless token files were already pre-filtered)
    vocab: set[str] | None = None
    if not args.no_vocab_filter:
        vocab_path = Path(args.vocab_path)
        if not vocab_path.exists():
            print(f"ERROR: Vocab file not found: {vocab_path}")
            sys.exit(1)
        print(f"Loading vocabulary from {vocab_path}...")
        vocab = load_vocab(vocab_path)
        print(f"  Vocabulary: {len(vocab):,} words")

    print("=" * 60)
    print(f"Stage 2: {args.n}-gram Counting")
    print("=" * 60)
    print(f"  Corpora: {', '.join(corpora)}")
    print(f"  N-gram size: {args.n}")
    print(f"  Min count: {args.min_count}")
    print(f"  Vocab filter: {'no' if args.no_vocab_filter else 'yes'}")

    start = time.time()

    # Count n-grams per corpus (in parallel)
    corpus_counters: dict[str, Counter] = {}
    work_items = [(tp, args.n, vocab) for tp in token_paths]

    if args.workers > 0 and len(work_items) > 1:
        ctx = get_context("fork")
        with ProcessPoolExecutor(
            max_workers=min(args.workers, len(work_items)),
            mp_context=ctx,
        ) as pool:
            for corpus_name, counter in pool.map(_count_worker, work_items):
                corpus_counters[corpus_name] = counter
                print(
                    f"  [{corpus_name}] {len(counter):,} unique {args.n}-grams, "
                    f"{sum(counter.values()):,} total"
                )
    else:
        for tp in token_paths:
            corpus_name, counter = _count_worker((tp, args.n, vocab))
            corpus_counters[corpus_name] = counter
            print(
                f"  [{corpus_name}] {len(counter):,} unique {args.n}-grams, "
                f"{sum(counter.values()):,} total"
            )

    # Save per-corpus TSVs
    print(f"\n  Saving per-corpus n-gram files (min_count={args.min_count})...")
    for corpus_name, counter in corpus_counters.items():
        out_path = output_dir / f"ngrams_{args.n}_{corpus_name}.tsv"
        written = save_ngrams_tsv(counter, out_path, args.min_count)
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"    {out_path.name}: {written:,} n-grams ({size_mb:.1f} MB)")

    # Raw merge (sum of counts across corpora)
    print(f"\n  Raw merge (sum of counts)...")
    raw_merged: Counter = Counter()
    for counter in corpus_counters.values():
        raw_merged.update(counter)

    raw_path = output_dir / f"ngrams_{args.n}_merged_raw.tsv"
    raw_written = save_ngrams_tsv(raw_merged, raw_path, args.min_count)
    size_mb = raw_path.stat().st_size / (1024 * 1024)
    print(f"    {raw_path.name}: {raw_written:,} n-grams ({size_mb:.1f} MB)")

    # Normalized merge (equal-weight per corpus)
    print(f"\n  Normalized merge (equal-weight per corpus)...")
    for name, counter in corpus_counters.items():
        total = sum(counter.values())
        print(f"    [{name}] {total:,} total -> weight 1/{len(corpus_counters)}")
    norm_merged = normalize_and_merge(corpus_counters)

    norm_path = output_dir / f"ngrams_{args.n}_merged.tsv"
    norm_written = save_ngrams_freq_tsv(norm_merged, norm_path)
    size_mb = norm_path.stat().st_size / (1024 * 1024)
    print(f"    {norm_path.name}: {norm_written:,} n-grams ({size_mb:.1f} MB)")

    # Summary stats
    elapsed = time.time() - start
    print(f"\n  Total unique {args.n}-grams (union): {len(norm_merged):,}")
    print(f"  Raw merged (min_count>={args.min_count}): {raw_written:,}")
    print(f"  Normalized merged (all): {norm_written:,}")
    print(f"  Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
