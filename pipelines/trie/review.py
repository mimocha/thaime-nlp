"""Trie dataset review CLI — filter, inspect, and export subsets.

A command-line tool for spot-checking the trie dataset. Filters the
dataset by various criteria (source, variant count, collisions) and
outputs summary stats plus an optional CSV export for further review.

This is a read-only inspection tool — it does not modify the trie
dataset. Fixes flow through the component dictionary, overrides file,
or word filters, then re-run the pipeline.

Usage:
    # Show overall dataset summary
    python -m pipelines.trie.review

    # Words with 0 variants (TLTK failures)
    python -m pipelines.trie.review --failures

    # Words unique to thwiki
    python -m pipelines.trie.review --source-only thwiki

    # Words in 4+ sources with low variant counts
    python -m pipelines.trie.review --source-min 4 --max-variants 5

    # High-collision romanization keys
    python -m pipelines.trie.review --collisions --min-collision 10

    # Export filtered results to CSV
    python -m pipelines.trie.review --failures --export failures.csv

    # Limit output rows
    python -m pipelines.trie.review --failures --limit 50
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pipelines.trie.config import OUTPUT_DIR


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


def apply_word_filters(entries: list[dict], args: argparse.Namespace) -> list[dict]:
    """Apply word-level filters based on CLI arguments.

    Returns the filtered subset of entries.
    """
    result = entries

    # Source filters
    if args.source:
        result = [e for e in result if args.source in e["sources"]]

    if args.source_only:
        result = [e for e in result if e["sources"] == [args.source_only]]

    if args.source_min is not None:
        result = [e for e in result if len(e["sources"]) >= args.source_min]

    if args.source_max is not None:
        result = [e for e in result if len(e["sources"]) <= args.source_max]

    # Variant count filters
    if args.failures:
        result = [e for e in result if len(e["romanizations"]) == 0]

    if args.min_variants is not None:
        result = [e for e in result if len(e["romanizations"]) >= args.min_variants]

    if args.max_variants is not None:
        result = [e for e in result if len(e["romanizations"]) <= args.max_variants]

    # Text search
    if args.search:
        query = args.search.lower()
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
        print("  (empty dataset)")
        return

    variant_counts = [len(e["romanizations"]) for e in entries]
    total_keys = sum(variant_counts)
    failures = sum(1 for vc in variant_counts if vc == 0)

    print(f"  Words:          {total:>10,}")
    print(f"  Total keys:     {total_keys:>10,}")
    print(f"  Failures (0v):  {failures:>10,} ({failures * 100 / total:.1f}%)")

    if any(vc > 0 for vc in variant_counts):
        nonzero = [vc for vc in variant_counts if vc > 0]
        avg = sum(nonzero) / len(nonzero)
        nonzero.sort()
        median = nonzero[len(nonzero) // 2]
        print(f"  Avg variants:   {avg:>10.1f}")
        print(f"  Median:         {median:>10}")

    # Source distribution
    from collections import Counter
    source_counts = Counter()
    for e in entries:
        for s in e["sources"]:
            source_counts[s] += 1

    if source_counts:
        print(f"\n  Sources:")
        for name, count in source_counts.most_common():
            print(f"    {name:<14} {count:>8,} ({count * 100 / total:.1f}%)")


def print_filter_summary(
    filtered: list[dict], total: int, args: argparse.Namespace,
) -> None:
    """Print summary of the active filter and its results."""
    # Build filter description
    filters = []
    if args.source:
        filters.append(f"source={args.source}")
    if args.source_only:
        filters.append(f"source-only={args.source_only}")
    if args.source_min is not None:
        filters.append(f"source-min={args.source_min}")
    if args.source_max is not None:
        filters.append(f"source-max={args.source_max}")
    if args.failures:
        filters.append("failures")
    if args.min_variants is not None:
        filters.append(f"min-variants={args.min_variants}")
    if args.max_variants is not None:
        filters.append(f"max-variants={args.max_variants}")
    if args.search:
        filters.append(f"search={args.search!r}")

    if filters:
        desc = ", ".join(filters)
        print(f"\n  Filter: {desc}")
        print(f"  Matched: {len(filtered):,} of {total:,} "
              f"({len(filtered) * 100 / total:.1f}%)")
    else:
        print(f"\n  No filter applied (showing all {total:,} words)")


# ---------------------------------------------------------------------------
# Word display
# ---------------------------------------------------------------------------


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
        print("  (no entries)")
        return

    # Header
    if show_romanizations:
        print(f"\n  {'ID':>6}  {'Thai':<16} {'Vars':>5} {'Srcs':>4}  "
              f"Sources                   Romanizations")
        print(f"  {'-' * 100}")
    else:
        print(f"\n  {'ID':>6}  {'Thai':<16} {'Vars':>5} {'Srcs':>4}  Sources")
        print(f"  {'-' * 60}")

    for e in subset:
        sources = "|".join(e["sources"])
        n_vars = len(e["romanizations"])

        if show_romanizations:
            # Show first few romanizations inline, truncated
            romans = ", ".join(e["romanizations"][:8])
            if len(e["romanizations"]) > 8:
                romans += f", ... (+{len(e['romanizations']) - 8})"
            print(f"  {e['word_id']:>6}  {e['thai']:<16} {n_vars:>5} "
                  f"{len(e['sources']):>4}  {sources:<25} {romans}")
        else:
            print(f"  {e['word_id']:>6}  {e['thai']:<16} {n_vars:>5} "
                  f"{len(e['sources']):>4}  {sources}")

    shown = len(subset)
    remaining = len(entries) - offset - shown
    if remaining > 0:
        print(f"\n  ... {remaining:,} more entries (use --limit and --offset to paginate)")


# ---------------------------------------------------------------------------
# Collision mode
# ---------------------------------------------------------------------------


def run_collision_mode(dataset: dict, args: argparse.Namespace) -> None:
    """Display romanization key collisions."""
    min_collision = args.min_collision or 2

    # Build key -> words mapping
    key_to_words: dict[str, list[str]] = {}
    for entry in dataset["entries"]:
        for key in entry["romanizations"]:
            key_to_words.setdefault(key, []).append(entry["thai"])

    collisions = {
        k: v for k, v in key_to_words.items()
        if len(v) >= min_collision
    }

    print(f"\n  Collision keys (>= {min_collision} words): {len(collisions):,}")

    if args.search:
        query = args.search.lower()
        collisions = {
            k: v for k, v in collisions.items()
            if query in k
        }
        print(f"  After search filter: {len(collisions):,}")

    # Sort by collision count descending
    sorted_collisions = sorted(
        collisions.items(), key=lambda x: len(x[1]), reverse=True,
    )

    limit = args.limit or 50
    offset = args.offset or 0
    subset = sorted_collisions[offset:offset + limit]

    if args.export:
        _export_collisions_csv(sorted_collisions, args.export)
        return

    print(f"\n  {'Key':<20} {'Words':>6}  Thai words")
    print(f"  {'-' * 80}")

    for key, words in subset:
        display = ", ".join(words[:10])
        if len(words) > 10:
            display += f", ... (+{len(words) - 10})"
        print(f"  {key:<20} {len(words):>6}  {display}")

    remaining = len(sorted_collisions) - offset - len(subset)
    if remaining > 0:
        print(f"\n  ... {remaining:,} more keys")


def _export_collisions_csv(
    collisions: list[tuple[str, list[str]]], path: str,
) -> None:
    """Export collision data to CSV."""
    out = Path(path)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["romanization_key", "word_count", "thai_words"])
        for key, words in collisions:
            writer.writerow([key, len(words), "|".join(words)])
    print(f"  Exported {len(collisions):,} collision keys to {out}")


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
    print(f"  Exported {len(entries):,} entries to {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review and inspect the trie dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                                  Show dataset summary
  %(prog)s --failures                       Words with 0 variants
  %(prog)s --source-only thwiki             Words unique to thwiki
  %(prog)s --source-min 4 --max-variants 5  High-confidence, low-variant words
  %(prog)s --collisions --min-collision 10  Keys mapping to 10+ words
  %(prog)s --failures --export out.csv      Export failures to CSV
  %(prog)s --search kaw                     Search by romanization key
""",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help=f"Path to trie_dataset.json (default: {OUTPUT_DIR / 'trie_dataset.json'})",
    )

    # Source filters
    source_group = parser.add_argument_group("source filters")
    source_group.add_argument(
        "--source",
        type=str,
        help="Words that appear in this source (e.g., thwiki, pythainlp)",
    )
    source_group.add_argument(
        "--source-only",
        type=str,
        help="Words that appear ONLY in this source",
    )
    source_group.add_argument(
        "--source-min",
        type=int,
        default=None,
        help="Words appearing in at least N sources",
    )
    source_group.add_argument(
        "--source-max",
        type=int,
        default=None,
        help="Words appearing in at most N sources",
    )

    # Variant filters
    variant_group = parser.add_argument_group("variant filters")
    variant_group.add_argument(
        "--failures",
        action="store_true",
        help="Words with 0 variants (TLTK failures)",
    )
    variant_group.add_argument(
        "--min-variants",
        type=int,
        default=None,
        help="Words with at least N variants",
    )
    variant_group.add_argument(
        "--max-variants",
        type=int,
        default=None,
        help="Words with at most N variants",
    )

    # Collision mode
    collision_group = parser.add_argument_group("collision mode")
    collision_group.add_argument(
        "--collisions",
        action="store_true",
        help="Show romanization key collisions instead of words",
    )
    collision_group.add_argument(
        "--min-collision",
        type=int,
        default=None,
        help="Minimum words per key to show (default: 2)",
    )

    # Search and display
    display_group = parser.add_argument_group("search and display")
    display_group.add_argument(
        "--search",
        type=str,
        help="Search Thai words or romanization keys containing this string",
    )
    display_group.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum entries to display (0 = default per mode)",
    )
    display_group.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N entries (for pagination)",
    )
    display_group.add_argument(
        "--show-romanizations", "-r",
        action="store_true",
        help="Show romanization variants in word table",
    )

    # Export
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export filtered results to CSV file",
    )

    args = parser.parse_args()

    # Load dataset
    dataset_path = (
        Path(args.dataset) if args.dataset
        else OUTPUT_DIR / "trie_dataset.json"
    )
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}")
        print("  Run the pipeline first: python -m pipelines.trie.generate")
        sys.exit(1)

    print(f"Loading {dataset_path}...")
    dataset = load_dataset(dataset_path)
    entries = dataset["entries"]
    print(f"  {len(entries):,} words loaded")

    # Collision mode is separate
    if args.collisions:
        run_collision_mode(dataset, args)
        return

    # Check if any filter is active
    has_filter = any([
        args.source, args.source_only, args.source_min is not None,
        args.source_max is not None, args.failures,
        args.min_variants is not None, args.max_variants is not None,
        args.search,
    ])

    if not has_filter:
        # No filter — show dataset summary
        print(f"\n{'=' * 60}")
        print("Dataset Summary")
        print(f"{'=' * 60}")
        print_dataset_summary(entries)
        print(f"\nUse --help to see available filters.")
        return

    # Apply filters
    filtered = apply_word_filters(entries, args)
    print_filter_summary(filtered, len(entries), args)

    if not filtered:
        return

    # Print summary of filtered set
    print()
    print_dataset_summary(filtered)

    # Export or display
    if args.export:
        export_words_csv(filtered, args.export)
    else:
        limit = args.limit or 100
        print_word_table(
            filtered,
            limit=limit,
            offset=args.offset,
            show_romanizations=args.show_romanizations,
        )


if __name__ == "__main__":
    main()
