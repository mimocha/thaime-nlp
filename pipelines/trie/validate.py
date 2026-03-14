"""Validate the trie dataset against the benchmark and report coverage.

Checks:
1. Benchmark regression — recall of romanization keys from the benchmark.
2. Per-source coverage — success rates and variant counts by corpus source.
3. Collision summary — romanization keys mapping to multiple Thai words.

Usage:
    python -m pipelines trie validate
    python -m pipelines trie validate --dataset pipelines/outputs/trie/trie_dataset.json
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import click

from pipelines.config import REPO_ROOT, TrieConfig
from pipelines.console import console

_cfg = TrieConfig()

BENCHMARK_PATH = REPO_ROOT / "benchmarks" / "word-conversion" / "v0.2.0.csv"


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
    """Check what fraction of benchmark entries are covered by the trie dataset."""
    word_to_keys: dict[str, set[str]] = {}
    for entry in dataset["entries"]:
        word_to_keys[entry["thai"]] = set(entry["romanizations"])

    total = len(benchmark)
    hits = 0
    word_missing = 0
    key_missing = 0
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

    benchmark_words = {row["expected_thai"] for row in benchmark}
    vocab_words = set(word_to_keys.keys())
    words_covered = benchmark_words & vocab_words
    words_with_zero = {w for w in words_covered if not word_to_keys[w]}

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
    """Compute variant generation success and quality metrics per source."""
    source_stats: dict[str, dict] = {}

    for entry in dataset["entries"]:
        n_variants = len(entry["romanizations"])
        for source in entry["sources"]:
            if source not in source_stats:
                source_stats[source] = {
                    "total": 0, "success": 0, "failed": 0,
                    "variant_sum": 0, "unique_words": 0,
                }
            stats = source_stats[source]
            stats["total"] += 1
            if n_variants > 0:
                stats["success"] += 1
                stats["variant_sum"] += n_variants
            else:
                stats["failed"] += 1

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
                "total": 0, "success": 0, "failed": 0, "variant_sum": 0,
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
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--dataset", type=str, default=None,
    help="Path to trie_dataset.json",
)
@click.option(
    "--benchmark", type=str, default=None,
    help=f"Path to benchmark CSV (default: {BENCHMARK_PATH})",
)
@click.option(
    "--missed-output", type=str, default=None,
    help="Write missed benchmark entries to this CSV file",
)
def validate(dataset, benchmark, missed_output) -> None:
    """Benchmark regression check for the trie dataset."""
    trie_dir = _cfg.output_dir / "trie"
    dataset_path = Path(dataset) if dataset else trie_dir / "trie_dataset.json"
    benchmark_path = Path(benchmark) if benchmark else BENCHMARK_PATH

    if not dataset_path.exists():
        console.print(f"[red]ERROR: Dataset not found at {dataset_path}[/red]")
        console.print("  Run the pipeline first: python -m pipelines trie run")
        sys.exit(1)

    if not benchmark_path.exists():
        console.print(f"[red]ERROR: Benchmark not found at {benchmark_path}[/red]")
        sys.exit(1)

    console.print(f"Loading dataset from {dataset_path}...")
    with open(dataset_path, encoding="utf-8") as f:
        ds = json.load(f)
    console.print(f"  {len(ds['entries']):,} words loaded")

    console.print(f"Loading benchmark from {benchmark_path}...")
    bench = load_benchmark(benchmark_path)
    console.print(f"  {len(bench):,} entries loaded")

    # 1. Benchmark regression
    console.print(f"\n{'=' * 60}")
    console.print("Benchmark Regression (v0.2.0)")
    console.print(f"{'=' * 60}")

    results = check_benchmark_recall(ds, bench)

    console.print(f"  Total benchmark pairs:     {results['total_pairs']:>8,}")
    console.print(f"  Hits (key found):          {results['hits']:>8,}")
    console.print(f"  Recall:                    {results['recall']:>8.1%}")
    console.print()
    console.print(f"  Miss breakdown:")
    console.print(f"    Word not in vocab:       {results['word_missing']:>8,}")
    console.print(f"    Key not generated:       {results['key_missing']:>8,}")
    console.print()
    console.print(f"  Benchmark unique words:    {results['benchmark_unique_words']:>8,}")
    console.print(f"  Words found in vocab:      {results['words_in_vocab']:>8,}")
    console.print(f"  Words with 0 variants:     {results['words_with_zero_variants']:>8,}")

    in_vocab_total = results["total_pairs"] - results["word_missing"]
    if in_vocab_total > 0:
        adjusted_recall = results["hits"] / in_vocab_total
        console.print(f"\n  Adjusted recall (in-vocab): {adjusted_recall:>7.1%}")

    key_missed = [m for m in results["missed"] if m["reason"] == "key_not_generated"]
    if key_missed:
        word_miss_count = Counter(m["expected_thai"] for m in key_missed)
        console.print(f"\n  Top 20 words with most missed romanization keys:")
        for word, count in word_miss_count.most_common(20):
            console.print(f"    {word}: {count} keys missed")

    # Write missed entries
    missed_path = Path(missed_output) if missed_output else trie_dir / "benchmark_missed.csv"
    missed_path.parent.mkdir(parents=True, exist_ok=True)
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
    console.print(f"\n  Missed entries written to {missed_path}")

    # 2. Per-source coverage
    console.print(f"\n{'=' * 60}")
    console.print("Per-Source Coverage")
    console.print(f"{'=' * 60}")

    source_stats = report_per_source_coverage(ds)

    console.print(f"\n  {'Source':<14} {'Total':>8} {'Success':>8} {'Failed':>8} "
                   f"{'Rate':>7} {'Avg Var':>8} {'Unique':>8}")
    console.print(f"  {'-' * 70}")
    for name in sorted(source_stats.keys()):
        s = source_stats[name]
        rate = s["success"] / s["total"] if s["total"] else 0
        avg_var = s["variant_sum"] / s["success"] if s["success"] else 0
        console.print(
            f"  {name:<14} {s['total']:>8,} {s['success']:>8,} {s['failed']:>8,} "
            f"{rate:>6.1%} {avg_var:>8.1f} {s['unique_words']:>8,}"
        )

    # 3. Coverage by source count
    console.print(f"\n{'=' * 60}")
    console.print("Coverage by Source Count")
    console.print(f"{'=' * 60}")

    by_count = report_by_source_count(ds)

    console.print(f"\n  {'Sources':>8} {'Total':>8} {'Success':>8} {'Failed':>8} "
                   f"{'Rate':>7} {'Avg Var':>8}")
    console.print(f"  {'-' * 55}")
    for n in sorted(by_count.keys()):
        s = by_count[n]
        rate = s["success"] / s["total"] if s["total"] else 0
        avg_var = s["variant_sum"] / s["success"] if s["success"] else 0
        console.print(
            f"  {n:>8} {s['total']:>8,} {s['success']:>8,} {s['failed']:>8,} "
            f"{rate:>6.1%} {avg_var:>8.1f}"
        )

    # 4. Collision summary
    console.print(f"\n{'=' * 60}")
    console.print("Collision Summary")
    console.print(f"{'=' * 60}")

    key_to_words: dict[str, list[str]] = {}
    for entry in ds["entries"]:
        for key in entry["romanizations"]:
            key_to_words.setdefault(key, []).append(entry["thai"])

    total_keys = len(key_to_words)
    collision_keys = {k: v for k, v in key_to_words.items() if len(v) > 1}

    console.print(f"  Total unique romanization keys: {total_keys:>10,}")
    console.print(f"  Keys with 1 word (unambiguous): {total_keys - len(collision_keys):>10,}")
    console.print(f"  Keys with 2+ words (collision): {len(collision_keys):>10,}")
    if total_keys:
        console.print(f"  Collision rate:                 {len(collision_keys) / total_keys:>9.1%}")

    collision_sizes = Counter(len(v) for v in collision_keys.values())
    console.print(f"\n  Collision size distribution:")
    for size in sorted(collision_sizes.keys()):
        count = collision_sizes[size]
        console.print(f"    {size:>3} words: {count:>8,} keys")

    console.print(f"\n{'=' * 60}")
    console.print("Validation complete!")
    console.print(f"{'=' * 60}")


if __name__ == "__main__":
    validate()
