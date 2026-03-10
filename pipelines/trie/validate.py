"""Validate the trie dataset against the v0.2.0 benchmark and report coverage.

Checks:
1. Benchmark regression — recall of romanization keys from the benchmark.
2. Per-source coverage — success rates and variant counts by corpus source.
3. Collision summary — romanization keys mapping to multiple Thai words.

Usage (after running the pipeline):
    python -m pipelines.trie.validate
    python -m pipelines.trie.validate --dataset pipelines/trie/outputs/trie_dataset.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from pipelines.trie.config import OUTPUT_DIR

BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmarks" / "word-conversion" / "v0.2.0.csv"
)


# ---------------------------------------------------------------------------
# Benchmark regression
# ---------------------------------------------------------------------------


def load_benchmark(path: Path) -> list[dict]:
    """Load benchmark CSV as list of dicts."""
    entries = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entries.append(row)
    return entries


def check_benchmark_recall(
    dataset: dict,
    benchmark: list[dict],
) -> dict:
    """Check what fraction of benchmark entries are covered by the trie dataset.

    For each benchmark row (latin_input, expected_thai), checks:
    - Is expected_thai in the dataset vocabulary?
    - If so, is latin_input among its romanization keys?

    Returns a results dict with recall metrics and missed entries.
    """
    # Build lookup: thai_word -> set of romanization keys
    word_to_keys: dict[str, set[str]] = {}
    for entry in dataset["entries"]:
        word_to_keys[entry["thai"]] = set(entry["romanizations"])

    total = len(benchmark)
    hits = 0
    word_missing = 0  # Thai word not in vocabulary
    key_missing = 0   # Thai word exists but romanization key not found
    missed: list[dict] = []

    for row in benchmark:
        latin = row["latin_input"]
        thai = row["expected_thai"]

        if thai not in word_to_keys:
            word_missing += 1
            missed.append({
                "latin_input": latin,
                "expected_thai": thai,
                "reason": "word_not_in_vocab",
            })
        elif latin not in word_to_keys[thai]:
            key_missing += 1
            missed.append({
                "latin_input": latin,
                "expected_thai": thai,
                "reason": "key_not_generated",
                "available_keys": len(word_to_keys[thai]),
            })
        else:
            hits += 1

    # Unique Thai words in benchmark
    benchmark_words = {row["expected_thai"] for row in benchmark}
    vocab_words = set(word_to_keys.keys())
    words_covered = benchmark_words & vocab_words
    words_with_zero = {
        w for w in words_covered
        if not word_to_keys[w]
    }

    return {
        "total_pairs": total,
        "hits": hits,
        "recall": hits / total if total else 0,
        "word_missing": word_missing,
        "key_missing": key_missing,
        "benchmark_unique_words": len(benchmark_words),
        "words_in_vocab": len(words_covered),
        "words_with_zero_variants": len(words_with_zero),
        "missed": missed,
    }


# ---------------------------------------------------------------------------
# Per-source coverage
# ---------------------------------------------------------------------------


def report_per_source_coverage(dataset: dict) -> dict[str, dict]:
    """Compute variant generation success and quality metrics per source.

    Returns dict mapping source_name -> {total, success, failed, avg_variants, ...}.
    """
    source_stats: dict[str, dict] = {}

    for entry in dataset["entries"]:
        n_variants = len(entry["romanizations"])
        for source in entry["sources"]:
            if source not in source_stats:
                source_stats[source] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "variant_sum": 0,
                    "unique_words": 0,
                }
            stats = source_stats[source]
            stats["total"] += 1
            if n_variants > 0:
                stats["success"] += 1
                stats["variant_sum"] += n_variants
            else:
                stats["failed"] += 1

    # Count words unique to each source
    for entry in dataset["entries"]:
        if len(entry["sources"]) == 1:
            source = entry["sources"][0]
            if source in source_stats:
                source_stats[source]["unique_words"] += 1

    return source_stats


def report_by_source_count(dataset: dict) -> dict[int, dict]:
    """Compute metrics grouped by how many sources a word appears in."""
    by_count: dict[int, dict] = {}

    for entry in dataset["entries"]:
        n_sources = len(entry["sources"])
        n_variants = len(entry["romanizations"])

        if n_sources not in by_count:
            by_count[n_sources] = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "variant_sum": 0,
            }
        stats = by_count[n_sources]
        stats["total"] += 1
        if n_variants > 0:
            stats["success"] += 1
            stats["variant_sum"] += n_variants
        else:
            stats["failed"] += 1

    return by_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate trie dataset against benchmark and report coverage."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help=f"Path to trie_dataset.json (default: {OUTPUT_DIR / 'trie_dataset.json'})",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help=f"Path to benchmark CSV (default: {BENCHMARK_PATH})",
    )
    parser.add_argument(
        "--missed-output",
        type=str,
        default=None,
        help="Write missed benchmark entries to this CSV file",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else OUTPUT_DIR / "trie_dataset.json"
    benchmark_path = Path(args.benchmark) if args.benchmark else BENCHMARK_PATH

    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}")
        print("  Run the pipeline first: python -m pipelines.trie.generate")
        sys.exit(1)

    if not benchmark_path.exists():
        print(f"ERROR: Benchmark not found at {benchmark_path}")
        sys.exit(1)

    print(f"Loading dataset from {dataset_path}...")
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)
    print(f"  {len(dataset['entries']):,} words loaded")

    print(f"Loading benchmark from {benchmark_path}...")
    benchmark = load_benchmark(benchmark_path)
    print(f"  {len(benchmark):,} entries loaded")

    # -----------------------------------------------------------------------
    # 1. Benchmark regression
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Benchmark Regression (v0.2.0)")
    print(f"{'=' * 60}")

    results = check_benchmark_recall(dataset, benchmark)

    print(f"  Total benchmark pairs:     {results['total_pairs']:>8,}")
    print(f"  Hits (key found):          {results['hits']:>8,}")
    print(f"  Recall:                    {results['recall']:>8.1%}")
    print()
    print(f"  Miss breakdown:")
    print(f"    Word not in vocab:       {results['word_missing']:>8,}")
    print(f"    Key not generated:       {results['key_missing']:>8,}")
    print()
    print(f"  Benchmark unique words:    {results['benchmark_unique_words']:>8,}")
    print(f"  Words found in vocab:      {results['words_in_vocab']:>8,}")
    print(f"  Words with 0 variants:     {results['words_with_zero_variants']:>8,}")

    # Adjusted recall: exclude words not in vocab (out-of-vocabulary)
    in_vocab_total = results["total_pairs"] - results["word_missing"]
    if in_vocab_total > 0:
        adjusted_recall = results["hits"] / in_vocab_total
        print(f"\n  Adjusted recall (in-vocab): {adjusted_recall:>7.1%}")
        print(f"    (excludes {results['word_missing']:,} pairs where Thai word is not in vocabulary)")

    # Top missed keys by frequency
    key_missed = [m for m in results["missed"] if m["reason"] == "key_not_generated"]
    if key_missed:
        # Count by Thai word
        word_miss_count = Counter(m["expected_thai"] for m in key_missed)
        print(f"\n  Top 20 words with most missed romanization keys:")
        for word, count in word_miss_count.most_common(20):
            print(f"    {word}: {count} keys missed")

    # Write missed entries to CSV if requested
    missed_path = Path(args.missed_output) if args.missed_output else OUTPUT_DIR / "benchmark_missed.csv"
    with open(missed_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "latin_input", "expected_thai", "reason", "available_keys",
        ])
        writer.writeheader()
        for m in results["missed"]:
            writer.writerow({
                "latin_input": m["latin_input"],
                "expected_thai": m["expected_thai"],
                "reason": m["reason"],
                "available_keys": m.get("available_keys", ""),
            })
    print(f"\n  Missed entries written to {missed_path}")

    # -----------------------------------------------------------------------
    # 2. Per-source coverage
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Per-Source Coverage")
    print(f"{'=' * 60}")

    source_stats = report_per_source_coverage(dataset)

    print(f"\n  {'Source':<14} {'Total':>8} {'Success':>8} {'Failed':>8} "
          f"{'Rate':>7} {'Avg Var':>8} {'Unique':>8}")
    print(f"  {'-' * 70}")
    for name in sorted(source_stats.keys()):
        s = source_stats[name]
        rate = s["success"] / s["total"] if s["total"] else 0
        avg_var = s["variant_sum"] / s["success"] if s["success"] else 0
        print(
            f"  {name:<14} {s['total']:>8,} {s['success']:>8,} {s['failed']:>8,} "
            f"{rate:>6.1%} {avg_var:>8.1f} {s['unique_words']:>8,}"
        )

    # -----------------------------------------------------------------------
    # 3. Coverage by source count
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Coverage by Source Count")
    print(f"{'=' * 60}")

    by_count = report_by_source_count(dataset)

    print(f"\n  {'Sources':>8} {'Total':>8} {'Success':>8} {'Failed':>8} "
          f"{'Rate':>7} {'Avg Var':>8}")
    print(f"  {'-' * 55}")
    for n in sorted(by_count.keys()):
        s = by_count[n]
        rate = s["success"] / s["total"] if s["total"] else 0
        avg_var = s["variant_sum"] / s["success"] if s["success"] else 0
        print(
            f"  {n:>8} {s['total']:>8,} {s['success']:>8,} {s['failed']:>8,} "
            f"{rate:>6.1%} {avg_var:>8.1f}"
        )

    # -----------------------------------------------------------------------
    # 4. Collision summary
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Collision Summary")
    print(f"{'=' * 60}")

    key_to_words: dict[str, list[str]] = {}
    for entry in dataset["entries"]:
        for key in entry["romanizations"]:
            key_to_words.setdefault(key, []).append(entry["thai"])

    total_keys = len(key_to_words)
    collision_keys = {k: v for k, v in key_to_words.items() if len(v) > 1}

    print(f"  Total unique romanization keys: {total_keys:>10,}")
    print(f"  Keys with 1 word (unambiguous): {total_keys - len(collision_keys):>10,}")
    print(f"  Keys with 2+ words (collision): {len(collision_keys):>10,}")
    if total_keys:
        print(f"  Collision rate:                 {len(collision_keys) / total_keys:>9.1%}")

    # Distribution of collision sizes
    collision_sizes = Counter(len(v) for v in collision_keys.values())
    print(f"\n  Collision size distribution:")
    for size in sorted(collision_sizes.keys()):
        count = collision_sizes[size]
        print(f"    {size:>3} words: {count:>8,} keys")

    print(f"\n{'=' * 60}")
    print("Validation complete!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
