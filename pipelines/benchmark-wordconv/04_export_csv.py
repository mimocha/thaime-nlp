"""Step 4: Export reviewed entries to benchmark CSV format.

Takes the reviewed JSON file and exports approved + edited entries
to the CSV format defined in docs/benchmarks.md.

Each Thai word generates multiple CSV rows — one per romanization variant.
The RTGS form is always included. Each row maps a latin_input to the
expected Thai word.

Output: benchmarks/word-conversion/basic.csv

Usage:
    python -m pipelines.benchmark-wordconv.04_export_csv
    python -m pipelines.benchmark-wordconv.04_export_csv --output benchmarks/word-conversion/basic.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
BENCHMARK_DIR = REPO_ROOT / "benchmarks" / "word-conversion"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export reviewed benchmark entries to CSV."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input reviewed JSON (default: output/reviewed_benchmark.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: benchmarks/word-conversion/v0.2.0.csv)",
    )
    parser.add_argument(
        "--include-discarded",
        action="store_true",
        help="Also include discarded entries (for debugging)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be exported without writing",
    )
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else OUTPUT_DIR / "reviewed_benchmark.json"
    output_path = Path(args.output) if args.output else BENCHMARK_DIR / "v0.2.0.csv"

    # Load reviewed data
    if not input_path.exists():
        print(f"  ERROR: {input_path} not found")
        print(f"  Run step 03 (review CLI) first")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]

    # Filter to accepted entries
    if args.include_discarded:
        accepted = entries
    else:
        accepted = [
            e for e in entries
            if e["review_status"] in ("approved", "edited")
        ]

    if not accepted:
        print("  No approved/edited entries found!")
        print(f"  Total entries: {len(entries)}")
        status_dist = Counter(e["review_status"] for e in entries)
        for status, count in sorted(status_dist.items()):
            print(f"    {status}: {count}")
        sys.exit(1)

    # Generate CSV rows (one row per variant per word)
    rows: list[dict] = []
    for entry in accepted:
        thai_word = entry["thai_word"]
        category = entry["category"]
        difficulty = entry["difficulty"]
        notes = entry.get("notes", "")

        for variant in entry["variants"]:
            rows.append({
                "latin_input": variant,
                "expected_thai": thai_word,
                "category": category,
                "difficulty": difficulty,
                "notes": notes,
            })

    # Sort by category, then difficulty, then latin_input for readability
    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    rows.sort(key=lambda r: (
        r["category"],
        difficulty_order.get(r["difficulty"], 9),
        r["latin_input"],
    ))

    # Stats
    unique_thai = len(set(r["expected_thai"] for r in rows))
    unique_latin = len(set(r["latin_input"] for r in rows))
    cat_dist = Counter(r["category"] for r in rows)
    diff_dist = Counter(r["difficulty"] for r in rows)

    print("=" * 60)
    print("Benchmark Export Summary")
    print("=" * 60)
    print(f"  Accepted entries (Thai words):  {len(accepted)}")
    print(f"  Total CSV rows (variants):      {len(rows)}")
    print(f"  Unique latin inputs:            {unique_latin}")
    print(f"  Unique Thai words:              {unique_thai}")
    print(f"\n  Rows by category:")
    for cat, count in sorted(cat_dist.items()):
        print(f"    {cat}: {count}")
    print(f"\n  Rows by difficulty:")
    for diff, count in sorted(diff_dist.items()):
        print(f"    {diff}: {count}")

    if args.dry_run:
        print(f"\n  [DRY RUN] Would write {len(rows)} rows to {output_path}")
        print(f"\n  Sample rows:")
        for row in rows[:10]:
            print(f"    {row['latin_input']},{row['expected_thai']},"
                  f"{row['category']},{row['difficulty']}")
        return

    # Write CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["latin_input", "expected_thai", "category", "difficulty", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  Written to: {output_path}")
    print(f"  Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
