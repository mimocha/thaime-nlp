"""Validate n-gram coverage against the ranking benchmark.

Loads merged bigram and trigram count files, checks coverage of the
ranking benchmark entries, and reports statistics.

Usage:
    python -m pipelines ngram validate
"""

from __future__ import annotations

import csv
from pathlib import Path

import click

from pipelines.config import REPO_ROOT, NgramConfig
from pipelines.console import console
from src.utils.versioning import resolve_latest_version

_cfg = NgramConfig()

BENCHMARK_DIR = REPO_ROOT / "benchmarks" / "ranking" / "bigram"


def get_benchmark_path() -> Path:
    """Resolve the latest ranking benchmark by semantic version."""
    return resolve_latest_version(BENCHMARK_DIR, "v*.csv")


def load_ngram_tsv(path: Path) -> dict[tuple[str, ...], float]:
    """Load n-gram frequency TSV (normalized merge format)."""
    ngrams: dict[tuple[str, ...], float] = {}
    if not path.exists():
        return ngrams

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            freq = float(parts[-1])
            tokens = tuple(parts[:-1])
            ngrams[tokens] = freq
    return ngrams


def load_benchmark(path: Path | None = None) -> list[dict]:
    """Load ranking benchmark CSV."""
    if path is None:
        path = get_benchmark_path()
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("latin_input", "").startswith("#"):
                continue
            rows.append(row)
    return rows


def run_validation(ngram_dir: Path) -> None:
    """Run validation checks and print report."""
    bigram_path = ngram_dir / "ngrams_2_merged.tsv"
    trigram_path = ngram_dir / "ngrams_3_merged.tsv"
    unigram_path = ngram_dir / "ngrams_1_merged.tsv"

    console.print(f"  Loading n-gram data...")
    bigrams = load_ngram_tsv(bigram_path)
    trigrams = load_ngram_tsv(trigram_path)
    unigrams = load_ngram_tsv(unigram_path)
    console.print(f"    Unigrams: {len(unigrams):,}")
    console.print(f"    Bigrams:  {len(bigrams):,}")
    console.print(f"    Trigrams: {len(trigrams):,}")

    if not bigrams:
        console.print("  [yellow]WARNING: No bigram data found. Skipping benchmark coverage check.[/yellow]")
        return

    try:
        benchmark_path = get_benchmark_path()
    except FileNotFoundError:
        console.print(f"  [yellow]WARNING: No benchmark found in {BENCHMARK_DIR}[/yellow]")
        return

    console.print(f"\n  Loading benchmark from {benchmark_path.name}...")
    rows = load_benchmark(benchmark_path)
    console.print(f"    Total rows: {len(rows)}")

    # Coverage by row type
    type_counts: dict[str, int] = {}
    type_hits: dict[str, int] = {}
    total = 0
    total_hits = 0

    for row in rows:
        row_type = row.get("type", "unknown")
        context = row.get("context", "")
        expected = row.get("expected_top", "")

        type_counts[row_type] = type_counts.get(row_type, 0) + 1
        total += 1

        if not context or not expected:
            if expected and (expected,) in unigrams:
                type_hits[row_type] = type_hits.get(row_type, 0) + 1
                total_hits += 1
            continue

        bigram_key = (context, expected)
        if bigram_key in bigrams:
            type_hits[row_type] = type_hits.get(row_type, 0) + 1
            total_hits += 1

    console.print(f"\n  Benchmark coverage (bigram):")
    console.print(f"    {'Type':<12} {'Total':>6} {'Hits':>6} {'Coverage':>10}")
    console.print(f"    {'-' * 36}")
    for row_type in sorted(type_counts.keys()):
        count = type_counts[row_type]
        hits = type_hits.get(row_type, 0)
        pct = hits * 100 / count if count > 0 else 0
        console.print(f"    {row_type:<12} {count:>6} {hits:>6} {pct:>9.1f}%")

    overall_pct = total_hits * 100 / total if total > 0 else 0
    console.print(f"    {'-' * 36}")
    console.print(f"    {'TOTAL':<12} {total:>6} {total_hits:>6} {overall_pct:>9.1f}%")

    # Top-N most frequent bigrams
    console.print(f"\n  Top 20 most frequent bigrams:")
    sorted_bigrams = sorted(bigrams.items(), key=lambda x: x[1], reverse=True)
    for i, (ngram, freq) in enumerate(sorted_bigrams[:20]):
        console.print(f"    {i + 1:>3}. {ngram[0]} {ngram[1]}  ({freq:.6e})")

    if trigrams:
        console.print(f"\n  Top 10 most frequent trigrams:")
        sorted_trigrams = sorted(trigrams.items(), key=lambda x: x[1], reverse=True)
        for i, (ngram, freq) in enumerate(sorted_trigrams[:10]):
            console.print(f"    {i + 1:>3}. {' '.join(ngram)}  ({freq:.6e})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--output-dir", default=None, type=click.Path(),
    help="Directory containing n-gram TSV files",
)
def validate(output_dir) -> None:
    """Validate n-gram coverage against the ranking benchmark."""
    ngram_dir = Path(output_dir) if output_dir else _cfg.ngram_dir
    run_validation(ngram_dir)


if __name__ == "__main__":
    validate()
