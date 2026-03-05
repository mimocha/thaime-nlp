"""Evaluate the variant generator on the 80-word test set.

Produces:
- Coverage rate: % of words where at least one generated variant matches
  an expected informal romanization
- Noise rate: average % of generated variants that are NOT in the expected list
- Expansion factor: average number of variants per word
- Per-word detailed results table
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).parent))

from test_words import TEST_WORDS
from variant_generator import (
    DEFAULT_CONFIG,
    VariantConfig,
    analyze_word,
    generate_syllable_variants,
    generate_word_variants,
)


def evaluate_variants(
    test_words: list[dict],
    config: VariantConfig = DEFAULT_CONFIG,
) -> dict:
    """Run evaluation on the test word set.

    Returns a dict with overall metrics and per-word details.
    """
    results = []
    total_coverage = 0
    total_noise = 0
    total_variants = 0
    total_plausible_noise = 0

    for entry in test_words:
        thai = entry["thai"]
        expected = set(entry["expected_informal"])
        category = entry["category"]

        variants = generate_word_variants(thai, config)
        variant_set = set(variants)
        num_variants = len(variants)

        # Coverage: does the variant set include at least one expected form?
        matches = variant_set & expected
        has_coverage = len(matches) > 0

        # Noise: how many generated variants are NOT in the expected list?
        # Note: the expected list is intentionally small (3-4 per word),
        # so many valid-looking variants won't be in it. We assess noise
        # as the fraction of variants not matching ANY expected form.
        non_matching = variant_set - expected
        noise_count = len(non_matching)
        noise_rate = noise_count / num_variants if num_variants > 0 else 0.0

        if has_coverage:
            total_coverage += 1

        total_noise += noise_rate
        total_variants += num_variants

        results.append({
            "thai": thai,
            "category": category,
            "base_roman": variants[0] if variants else "",
            "num_variants": num_variants,
            "variants": variants,
            "expected": sorted(expected),
            "matches": sorted(matches),
            "has_coverage": has_coverage,
            "noise_rate": round(noise_rate, 3),
        })

    n = len(test_words)
    overall = {
        "total_words": n,
        "coverage_count": total_coverage,
        "coverage_rate": round(total_coverage / n, 4) if n > 0 else 0.0,
        "avg_noise_rate": round(total_noise / n, 4) if n > 0 else 0.0,
        "avg_variants_per_word": round(total_variants / n, 2) if n > 0 else 0.0,
        "total_variants": total_variants,
        "min_variants": min(r["num_variants"] for r in results),
        "max_variants": max(r["num_variants"] for r in results),
    }

    # Per-category breakdown
    categories = sorted(set(e["category"] for e in test_words))
    per_category = {}
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_n = len(cat_results)
        cat_coverage = sum(1 for r in cat_results if r["has_coverage"])
        cat_variants = sum(r["num_variants"] for r in cat_results)
        per_category[cat] = {
            "count": cat_n,
            "coverage_count": cat_coverage,
            "coverage_rate": round(cat_coverage / cat_n, 4) if cat_n > 0 else 0.0,
            "avg_variants": round(cat_variants / cat_n, 2) if cat_n > 0 else 0.0,
        }

    return {
        "overall": overall,
        "per_category": per_category,
        "details": results,
    }


def print_results(eval_results: dict) -> None:
    """Print formatted evaluation results."""
    overall = eval_results["overall"]
    per_cat = eval_results["per_category"]
    details = eval_results["details"]

    print("=" * 80)
    print("INFORMAL ROMANIZATION VARIANT GENERATOR - EVALUATION RESULTS")
    print("=" * 80)

    print(f"\n--- Overall Metrics ---")
    print(f"Total words evaluated:     {overall['total_words']}")
    print(f"Coverage rate:             {overall['coverage_rate']:.1%} "
          f"({overall['coverage_count']}/{overall['total_words']})")
    print(f"Avg noise rate:            {overall['avg_noise_rate']:.1%}")
    print(f"Avg variants per word:     {overall['avg_variants_per_word']:.1f}")
    print(f"Total variants generated:  {overall['total_variants']}")
    print(f"Min/Max variants per word: {overall['min_variants']}/{overall['max_variants']}")

    print(f"\n--- Per-Category Breakdown ---")
    print(f"{'Category':<15} {'Count':>5} {'Coverage':>10} {'Avg Variants':>14}")
    print("-" * 46)
    for cat, stats in sorted(per_cat.items()):
        print(f"{cat:<15} {stats['count']:>5} "
              f"{stats['coverage_rate']:>9.1%} "
              f"{stats['avg_variants']:>13.1f}")

    print(f"\n--- Per-Word Details ---")
    print(f"{'Thai':<20} {'#Var':>4} {'Cov':>4} {'Noise':>6}  "
          f"{'Matches':<30} {'All Variants'}")
    print("-" * 120)

    for r in details:
        cov_mark = "✓" if r["has_coverage"] else "✗"
        matches_str = ", ".join(r["matches"]) if r["matches"] else "-"
        variants_str = ", ".join(r["variants"][:8])
        if len(r["variants"]) > 8:
            variants_str += f" ... (+{len(r['variants']) - 8})"
        print(f"{r['thai']:<20} {r['num_variants']:>4} {cov_mark:>4} "
              f"{r['noise_rate']:>5.0%}  {matches_str:<30} {variants_str}")


def print_syllable_analysis(test_words: list[dict]) -> None:
    """Print detailed syllable analysis for all test words."""
    print("\n" + "=" * 80)
    print("SYLLABLE ANALYSIS")
    print("=" * 80)

    for entry in test_words:
        thai = entry["thai"]
        syllables = analyze_word(thai)
        print(f"\n{thai}:")
        for syl in syllables:
            variants = generate_syllable_variants(syl)
            print(f"  {syl.thai_text}: roman={syl.romanization!r} "
                  f"vowel={syl.vowel_nucleus!r} "
                  f"long={syl.has_long_vowel} open={syl.is_open_syllable} "
                  f"init={syl.initial_cluster!r} final={syl.final_consonant!r} "
                  f"→ {variants}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate variant generator")
    parser.add_argument("--detail", action="store_true",
                        help="Show syllable analysis")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    config = DEFAULT_CONFIG
    eval_results = evaluate_variants(TEST_WORDS, config)

    if args.json:
        print(json.dumps(eval_results, ensure_ascii=False, indent=2))
    else:
        print_results(eval_results)

    if args.detail:
        print_syllable_analysis(TEST_WORDS)
