"""Trie dataset review CLI — filter, inspect, and export subsets.

A command-line tool for spot-checking the trie dataset. Filters the
dataset by various criteria (source, variant count, collisions) and
outputs summary stats plus an optional CSV export for further review.

Usage:
    python -m pipelines trie review
    python -m pipelines trie review --failures
    python -m pipelines trie review --source-only thwiki
    python -m pipelines trie review --collisions --min-collision 10
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import click

from pipelines.config import TrieConfig
from pipelines.console import console

_cfg = TrieConfig()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> dict:
    """Load trie dataset JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Word filters
# ---------------------------------------------------------------------------


def apply_word_filters(
    entries: list[dict],
    source: str | None,
    source_only: str | None,
    source_min: int | None,
    source_max: int | None,
    failures: bool,
    min_variants: int | None,
    max_variants: int | None,
    search: str | None,
) -> list[dict]:
    """Apply word-level filters based on CLI arguments."""
    result = entries

    if source:
        result = [e for e in result if source in e["sources"]]
    if source_only:
        result = [e for e in result if e["sources"] == [source_only]]
    if source_min is not None:
        result = [e for e in result if len(e["sources"]) >= source_min]
    if source_max is not None:
        result = [e for e in result if len(e["sources"]) <= source_max]
    if failures:
        result = [e for e in result if len(e["romanizations"]) == 0]
    if min_variants is not None:
        result = [e for e in result if len(e["romanizations"]) >= min_variants]
    if max_variants is not None:
        result = [e for e in result if len(e["romanizations"]) <= max_variants]
    if search:
        query = search.lower()
        result = [
            e for e in result
            if query in e["thai"] or any(query in r for r in e["romanizations"])
        ]

    return result


# ---------------------------------------------------------------------------
# Summary display
# ---------------------------------------------------------------------------


def print_dataset_summary(entries: list[dict]) -> None:
    """Print overall dataset summary statistics."""
    total = len(entries)
    if total == 0:
        console.print("  (empty dataset)")
        return

    variant_counts = [len(e["romanizations"]) for e in entries]
    total_keys = sum(variant_counts)
    fail_count = sum(1 for vc in variant_counts if vc == 0)

    console.print(f"  Words:          {total:>10,}")
    console.print(f"  Total keys:     {total_keys:>10,}")
    console.print(f"  Failures (0v):  {fail_count:>10,} ({fail_count * 100 / total:.1f}%)")

    if any(vc > 0 for vc in variant_counts):
        nonzero = [vc for vc in variant_counts if vc > 0]
        avg = sum(nonzero) / len(nonzero)
        nonzero.sort()
        median = nonzero[len(nonzero) // 2]
        console.print(f"  Avg variants:   {avg:>10.1f}")
        console.print(f"  Median:         {median:>10}")

    source_counts = Counter()
    for e in entries:
        for s in e["sources"]:
            source_counts[s] += 1

    if source_counts:
        console.print(f"\n  Sources:")
        for name, count in source_counts.most_common():
            console.print(f"    {name:<14} {count:>8,} ({count * 100 / total:.1f}%)")


def print_word_table(
    entries: list[dict],
    limit: int = 0,
    offset: int = 0,
    show_romanizations: bool = False,
) -> None:
    """Print a table of word entries."""
    subset = entries[offset:]
    if limit > 0:
        subset = subset[:limit]

    if not subset:
        console.print("  (no entries)")
        return

    if show_romanizations:
        console.print(f"\n  {'ID':>6}  {'Thai':<16} {'Vars':>5} {'Srcs':>4}  "
                       f"Sources                   Romanizations")
        console.print(f"  {'-' * 100}")
    else:
        console.print(f"\n  {'ID':>6}  {'Thai':<16} {'Vars':>5} {'Srcs':>4}  Sources")
        console.print(f"  {'-' * 60}")

    for e in subset:
        sources = "|".join(e["sources"])
        n_vars = len(e["romanizations"])

        if show_romanizations:
            romans = ", ".join(e["romanizations"][:8])
            if len(e["romanizations"]) > 8:
                romans += f", ... (+{len(e['romanizations']) - 8})"
            console.print(f"  {e['word_id']:>6}  {e['thai']:<16} {n_vars:>5} "
                           f"{len(e['sources']):>4}  {sources:<25} {romans}")
        else:
            console.print(f"  {e['word_id']:>6}  {e['thai']:<16} {n_vars:>5} "
                           f"{len(e['sources']):>4}  {sources}")

    shown = len(subset)
    remaining = len(entries) - offset - shown
    if remaining > 0:
        console.print(f"\n  ... {remaining:,} more entries (use --limit and --offset to paginate)")


# ---------------------------------------------------------------------------
# Collision mode
# ---------------------------------------------------------------------------


def run_collision_mode(
    dataset: dict,
    min_collision: int,
    search: str | None,
    limit: int,
    offset: int,
    export_path: str | None,
) -> None:
    """Display romanization key collisions."""
    key_to_words: dict[str, list[str]] = {}
    for entry in dataset["entries"]:
        for key in entry["romanizations"]:
            key_to_words.setdefault(key, []).append(entry["thai"])

    collisions = {k: v for k, v in key_to_words.items() if len(v) >= min_collision}

    console.print(f"\n  Collision keys (>= {min_collision} words): {len(collisions):,}")

    if search:
        query = search.lower()
        collisions = {k: v for k, v in collisions.items() if query in k}
        console.print(f"  After search filter: {len(collisions):,}")

    sorted_collisions = sorted(
        collisions.items(), key=lambda x: len(x[1]), reverse=True,
    )

    if export_path:
        out = Path(export_path)
        with open(out, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["romanization_key", "word_count", "thai_words"])
            for key, words in sorted_collisions:
                writer.writerow([key, len(words), "|".join(words)])
        console.print(f"  Exported {len(sorted_collisions):,} collision keys to {out}")
        return

    subset = sorted_collisions[offset:offset + limit]

    console.print(f"\n  {'Key':<20} {'Words':>6}  Thai words")
    console.print(f"  {'-' * 80}")

    for key, words in subset:
        display = ", ".join(words[:10])
        if len(words) > 10:
            display += f", ... (+{len(words) - 10})"
        console.print(f"  {key:<20} {len(words):>6}  {display}")

    remaining = len(sorted_collisions) - offset - len(subset)
    if remaining > 0:
        console.print(f"\n  ... {remaining:,} more keys")


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def export_words_csv(entries: list[dict], path: str) -> None:
    """Export filtered word entries to CSV."""
    out = Path(path)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "word_id", "thai_word", "variant_count",
            "source_count", "sources", "romanizations",
        ])
        for e in entries:
            writer.writerow([
                e["word_id"],
                e["thai"],
                len(e["romanizations"]),
                len(e["sources"]),
                "|".join(e["sources"]),
                "|".join(e["romanizations"]),
            ])
    console.print(f"  Exported {len(entries):,} entries to {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--dataset", type=str, default=None, help="Path to trie_dataset.json")
# Source filters
@click.option("--source", type=str, default=None, help="Words that appear in this source")
@click.option("--source-only", type=str, default=None, help="Words that appear ONLY in this source")
@click.option("--source-min", type=int, default=None, help="Words appearing in at least N sources")
@click.option("--source-max", type=int, default=None, help="Words appearing in at most N sources")
# Variant filters
@click.option("--failures", is_flag=True, help="Words with 0 variants (TLTK failures)")
@click.option("--min-variants", type=int, default=None, help="Words with at least N variants")
@click.option("--max-variants", type=int, default=None, help="Words with at most N variants")
# Collision mode
@click.option("--collisions", is_flag=True, help="Show romanization key collisions instead of words")
@click.option("--min-collision", type=int, default=None, help="Minimum words per key to show (default: 2)")
# Search and display
@click.option("--search", type=str, default=None, help="Search Thai words or romanization keys")
@click.option("--limit", type=int, default=0, help="Maximum entries to display")
@click.option("--offset", type=int, default=0, help="Skip first N entries")
@click.option("--show-romanizations", "-r", is_flag=True, help="Show romanization variants in word table")
# Export
@click.option("--export", "export_path", type=str, default=None, help="Export filtered results to CSV file")
def review(dataset, source, source_only, source_min, source_max,
           failures, min_variants, max_variants, collisions, min_collision,
           search, limit, offset, show_romanizations, export_path) -> None:
    """Read-only inspection of the trie dataset."""
    trie_dir = _cfg.output_dir / "trie"
    dataset_path = Path(dataset) if dataset else trie_dir / "trie_dataset.json"

    if not dataset_path.exists():
        console.print(f"[red]ERROR: Dataset not found at {dataset_path}[/red]")
        console.print("  Run the pipeline first: python -m pipelines trie run")
        sys.exit(1)

    console.print(f"Loading {dataset_path}...")
    ds = load_dataset(dataset_path)
    entries = ds["entries"]
    console.print(f"  {len(entries):,} words loaded")

    # Collision mode
    if collisions:
        run_collision_mode(
            ds, min_collision or 2, search, limit or 50, offset, export_path,
        )
        return

    # Check if any filter is active
    has_filter = any([
        source, source_only, source_min is not None, source_max is not None,
        failures, min_variants is not None, max_variants is not None, search,
    ])

    if not has_filter:
        console.print(f"\n{'=' * 60}")
        console.print("Dataset Summary")
        console.print(f"{'=' * 60}")
        print_dataset_summary(entries)
        console.print(f"\nUse --help to see available filters.")
        return

    filtered = apply_word_filters(
        entries, source, source_only, source_min, source_max,
        failures, min_variants, max_variants, search,
    )

    console.print(f"\n  Matched: {len(filtered):,} of {len(entries):,} "
                   f"({len(filtered) * 100 / len(entries):.1f}%)")

    if not filtered:
        return

    console.print()
    print_dataset_summary(filtered)

    if export_path:
        export_words_csv(filtered, export_path)
    else:
        print_word_table(
            filtered, limit=limit or 100, offset=offset,
            show_romanizations=show_romanizations,
        )


if __name__ == "__main__":
    review()
