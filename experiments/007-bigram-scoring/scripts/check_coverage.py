"""Check benchmark bigram coverage against extracted n-gram data.

Reports what percentage of benchmark bigrams appear in the n-gram
frequency tables, broken down by type (baseline/bigram/compound)
and by corpus source.

Usage:
    python -m experiments.007-bigram-scoring.scripts.check_coverage
    python -m experiments.007-bigram-scoring.scripts.check_coverage --benchmark benchmarks/ranking/bigram/v0.1.1.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .config import CORPORA, OUTPUT_DIR


BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "benchmarks" / "ranking" / "bigram" / "v0.1.1.csv"
)


def load_benchmark(path: Path) -> list[dict]:
    """Load benchmark CSV, skipping comment lines.

    Each row becomes a dict with keys: latin_input, context, expected_top,
    valid_alternatives, type, notes.
    """
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            first_val = row.get("latin_input", "")
            if first_val.startswith("#"):
                continue
            rows.append(row)
    return rows


def load_ngram_set(path: Path) -> set[tuple[str, str]]:
    """Load bigram TSV into a set of (word1, word2) tuples."""
    bigrams = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:  # word1, word2, count/freq
                bigrams.add((parts[0], parts[1]))
    return bigrams


def _pct(num: int, denom: int) -> str:
    """Format percentage string, handling zero denominator."""
    if denom == 0:
        return "  N/A"
    return f"{num / denom * 100:5.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check benchmark bigram coverage against n-gram data."
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=str(BENCHMARK_PATH),
        help=f"Path to benchmark CSV (default: {BENCHMARK_PATH})",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help=f"Directory with n-gram TSVs (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=2,
        help="N-gram size (default: 2)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else OUTPUT_DIR
    benchmark_path = Path(args.benchmark)

    if not benchmark_path.exists():
        print(f"ERROR: Benchmark not found: {benchmark_path}")
        sys.exit(1)

    # Load benchmark
    rows = load_benchmark(benchmark_path)
    print(f"Loaded {len(rows)} benchmark rows from {benchmark_path.name}")

    # Categorize by type
    has_type_col = "type" in rows[0] if rows else False
    baseline_rows = []
    bigram_rows = []
    compound_rows = []

    for row in rows:
        row_type = row.get("type", "")
        if not row["context"]:
            baseline_rows.append(row)
        elif row_type == "compound":
            compound_rows.append(row)
        else:
            bigram_rows.append(row)

    print(f"  Baseline (no context): {len(baseline_rows)}")
    print(f"  Bigram (context):      {len(bigram_rows)}")
    print(f"  Compound (context):    {len(compound_rows)}")

    # Build bigram sets per type
    def extract_bigrams(row_list):
        expected = set()
        all_valid = set()
        for row in row_list:
            ctx = row["context"]
            if not ctx:
                continue
            exp = row["expected_top"]
            expected.add((ctx, exp))
            all_valid.add((ctx, exp))
            alts = row.get("valid_alternatives", "")
            if alts:
                for alt in alts.split("|"):
                    alt = alt.strip()
                    if alt:
                        all_valid.add((ctx, alt))
        return expected, all_valid

    bigram_expected, bigram_valid = extract_bigrams(bigram_rows)
    compound_expected, compound_valid = extract_bigrams(compound_rows)
    all_expected, all_valid = extract_bigrams(bigram_rows + compound_rows)

    print(f"\n  Bigram rows:   {len(bigram_expected)} expected, {len(bigram_valid)} valid")
    print(f"  Compound rows: {len(compound_expected)} expected, {len(compound_valid)} valid")
    print(f"  All context:   {len(all_expected)} expected, {len(all_valid)} valid")

    # Check coverage against each n-gram source
    print(f"\n{'=' * 74}")
    print("Coverage Report")
    print(f"{'=' * 74}")

    sources = CORPORA + ["merged_raw", "merged"]
    for source in sources:
        tsv_path = data_dir / f"ngrams_{args.n}_{source}.tsv"
        if not tsv_path.exists():
            print(f"\n  [{source}] File not found, skipping")
            continue

        ngram_set = load_ngram_set(tsv_path)

        bg_found = bigram_expected & ngram_set
        cp_found = compound_expected & ngram_set
        all_found = all_expected & ngram_set
        bg_valid_found = bigram_valid & ngram_set
        all_valid_found = all_valid & ngram_set

        print(f"\n  [{source}] ({len(ngram_set):,} bigrams in file)")
        print(f"    Bigram expected:   {len(bg_found):>4}/{len(bigram_expected):<4} ({_pct(len(bg_found), len(bigram_expected))})")
        print(f"    Compound expected: {len(cp_found):>4}/{len(compound_expected):<4} ({_pct(len(cp_found), len(compound_expected))})")
        print(f"    All expected:      {len(all_found):>4}/{len(all_expected):<4} ({_pct(len(all_found), len(all_expected))})")
        print(f"    Bigram valid:      {len(bg_valid_found):>4}/{len(bigram_valid):<4} ({_pct(len(bg_valid_found), len(bigram_valid))})")
        print(f"    All valid:         {len(all_valid_found):>4}/{len(all_valid):<4} ({_pct(len(all_valid_found), len(all_valid))})")

    # Detailed miss analysis on the merged normalized file
    merged_path = data_dir / f"ngrams_{args.n}_merged.tsv"
    if not merged_path.exists():
        return

    ngram_set = load_ngram_set(merged_path)

    # Bigram misses (the important ones)
    bigram_missed = bigram_expected - ngram_set
    if bigram_missed:
        print(f"\n{'=' * 74}")
        print(f"Missing BIGRAM expected pairs (not in merged normalized): {len(bigram_missed)}")
        print(f"{'=' * 74}")
        for ctx, exp in sorted(bigram_missed):
            matching = [
                r for r in bigram_rows
                if r["context"] == ctx and r["expected_top"] == exp
            ]
            note = matching[0]["notes"] if matching else ""
            print(f"  ({ctx}, {exp})  — {note}")

    # Compound misses (expected — less critical for bigram evaluation)
    compound_missed = compound_expected - ngram_set
    if compound_missed:
        print(f"\n{'=' * 74}")
        print(f"Missing COMPOUND expected pairs (not in merged normalized): {len(compound_missed)}")
        print(f"{'=' * 74}")
        for ctx, exp in sorted(compound_missed):
            matching = [
                r for r in compound_rows
                if r["context"] == ctx and r["expected_top"] == exp
            ]
            note = matching[0]["notes"] if matching else ""
            print(f"  ({ctx}, {exp})  — {note}")

    # Valid alternative summary
    bigram_valid_missed = bigram_valid - ngram_set
    alt_missed = bigram_valid_missed - bigram_missed
    if alt_missed:
        print(f"\n  Missing bigram alternative pairs: {len(alt_missed)}")
        print(f"  (Valid but not expected-top, less critical)")


if __name__ == "__main__":
    main()
