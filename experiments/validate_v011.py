"""Commit 3 validation: Run variant generator v2 against benchmark v0.1.1.

Measures:
- Entry-level reproduction rate (does the generator produce each benchmark latin_input
  for the corresponding expected_thai word?)
- Word-level reproduction rate (for each unique Thai word, does the generator
  cover all its benchmark entries?)
- Categorize misses by type (dictionary gap, decomposition issue, structural)
- Variant count statistics
"""

from __future__ import annotations

import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.variant_generator import analyze_word, generate_word_variants
from src.utils.benchmark import load_benchmark


def main():
    # Load benchmark v0.1.1
    benchmark = load_benchmark("benchmarks/word-conversion/v0.1.1.csv")
    print(f"Loaded benchmark v0.1.1: {len(benchmark)} entries")

    # Group benchmark entries by Thai word
    # Each Thai word -> list of expected latin inputs
    word_entries: dict[str, list[str]] = defaultdict(list)
    for row in benchmark:
        thai = row["expected_thai"]
        latin = row["latin_input"]
        word_entries[thai].append(latin)

    unique_words = sorted(word_entries.keys())
    print(f"Unique Thai words: {len(unique_words)}")
    print()

    # Run generator on each unique word
    hits = 0
    misses = 0
    total_entries = len(benchmark)

    word_hits = 0
    word_misses = 0

    miss_details: list[dict] = []
    variant_counts: list[int] = []
    word_results: list[dict] = []

    start = time.time()
    for thai_word in unique_words:
        expected_latins = word_entries[thai_word]

        # Generate variants (use high cap for validation)
        variants = generate_word_variants(thai_word, max_variants=200)
        variant_set = set(variants)
        variant_counts.append(len(variants))

        # Check each expected latin
        word_all_hit = True
        word_hit_count = 0
        word_miss_count = 0
        for latin in expected_latins:
            if latin in variant_set:
                hits += 1
                word_hit_count += 1
            else:
                misses += 1
                word_all_hit = False
                word_miss_count += 1
                miss_details.append({
                    "thai": thai_word,
                    "expected_latin": latin,
                    "generated_variants": variants[:10],  # first 10 for brevity
                    "total_variants": len(variants),
                })

        if word_all_hit:
            word_hits += 1
        else:
            word_misses += 1

        word_results.append({
            "thai": thai_word,
            "expected_count": len(expected_latins),
            "hit_count": word_hit_count,
            "miss_count": word_miss_count,
            "variant_count": len(variants),
            "expected_latins": expected_latins,
            "generated_variants": variants,
        })

    elapsed = time.time() - start

    # --- Results ---
    print("=" * 70)
    print("BENCHMARK v0.1.1 VALIDATION RESULTS")
    print("=" * 70)
    print()

    # Entry-level metrics
    entry_rate = hits / total_entries * 100 if total_entries else 0
    print(f"Entry-level reproduction rate: {hits}/{total_entries} = {entry_rate:.1f}%")
    print(f"  Hits: {hits}  |  Misses: {misses}")
    print()

    # Word-level metrics (all benchmark entries for that word reproduced)
    total_words = len(unique_words)
    word_rate = word_hits / total_words * 100 if total_words else 0
    print(f"Word-level full coverage rate: {word_hits}/{total_words} = {word_rate:.1f}%")
    print(f"  Fully covered: {word_hits}  |  Partially/not covered: {word_misses}")
    print()

    # Variant count stats
    if variant_counts:
        import statistics
        print("Variant count statistics:")
        print(f"  Mean:   {statistics.mean(variant_counts):.1f}")
        print(f"  Median: {statistics.median(variant_counts):.1f}")
        print(f"  Min:    {min(variant_counts)}")
        print(f"  Max:    {max(variant_counts)}")
        print(f"  Stdev:  {statistics.stdev(variant_counts):.1f}" if len(variant_counts) > 1 else "")
        # Distribution buckets
        buckets = defaultdict(int)
        for c in variant_counts:
            if c <= 5:
                buckets["1-5"] += 1
            elif c <= 10:
                buckets["6-10"] += 1
            elif c <= 20:
                buckets["11-20"] += 1
            elif c <= 50:
                buckets["21-50"] += 1
            elif c <= 100:
                buckets["51-100"] += 1
            else:
                buckets["100+"] += 1
        print("  Distribution:")
        for bucket in ["1-5", "6-10", "11-20", "21-50", "51-100", "100+"]:
            if bucket in buckets:
                print(f"    {bucket:>6}: {buckets[bucket]} words")
    print()

    print(f"Elapsed time: {elapsed:.1f}s")
    print()

    # Miss analysis
    if miss_details:
        print("=" * 70)
        print(f"MISSED ENTRIES ({len(miss_details)} total)")
        print("=" * 70)
        print()

        # Group misses by Thai word for readability
        misses_by_word: dict[str, list[dict]] = defaultdict(list)
        for m in miss_details:
            misses_by_word[m["thai"]].append(m)

        for thai, word_misses_list in sorted(misses_by_word.items()):
            # Get the word result for context
            wr = next(r for r in word_results if r["thai"] == thai)
            hit_rate = wr["hit_count"] / wr["expected_count"] * 100

            # Get analysis for context
            syllables = analyze_word(thai)
            decomp = " | ".join(
                f"[{c.onset}/{c.vowel}/{c.coda}]" for c in syllables
            )

            print(f"  {thai} ({wr['hit_count']}/{wr['expected_count']} = {hit_rate:.0f}% hit)")
            print(f"    g2p decomposition: {decomp}")
            print(f"    generated ({wr['variant_count']} total): {wr['generated_variants'][:8]}...")
            for m in word_misses_list:
                print(f"    MISS: {m['expected_latin']!r}")
            print()

    # Write detailed CSV for further analysis
    output_path = REPO_ROOT / "experiments" / "v011_validation_results.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "thai_word", "expected_count", "hit_count", "miss_count",
            "variant_count", "hit_rate", "missed_latins", "sample_variants"
        ])
        for wr in word_results:
            missed = [
                l for l in wr["expected_latins"]
                if l not in set(wr["generated_variants"])
            ]
            writer.writerow([
                wr["thai"],
                wr["expected_count"],
                wr["hit_count"],
                wr["miss_count"],
                wr["variant_count"],
                f"{wr['hit_count'] / wr['expected_count'] * 100:.0f}%",
                "; ".join(missed),
                "; ".join(wr["generated_variants"][:10]),
            ])
    print(f"Detailed results written to: {output_path}")


if __name__ == "__main__":
    main()
