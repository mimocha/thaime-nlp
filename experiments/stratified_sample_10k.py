"""Stratified sampling of 10K draft benchmark for manual review.

Produces ~300 words sampled across:
- Frequency tier: top-500, 501-2000, 2001-5000, 5001-10000
- Syllable count: 1, 2, 3, 4+
- Component diversity: low (<=5 variants), medium (6-30), high (>30)

Outputs a CSV for the maintainer to review, plus summary statistics
about dictionary coverage across the full 10K vocabulary.

Usage:
    python experiments/stratified_sample_10k.py
    python experiments/stratified_sample_10k.py --input path/to/draft_benchmark.json
    python experiments/stratified_sample_10k.py --sample-size 200
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "pipelines" / "benchmark-wordconv" / "output" / "draft_benchmark.json"
DEFAULT_OUTPUT = REPO_ROOT / "experiments" / "10k_stratified_sample.csv"


def frequency_tier(rank: int) -> str:
    if rank <= 500:
        return "top-500"
    elif rank <= 2000:
        return "501-2000"
    elif rank <= 5000:
        return "2001-5000"
    else:
        return "5001-10000"


def syllable_bucket(count: int) -> str:
    if count == 1:
        return "1-syl"
    elif count == 2:
        return "2-syl"
    elif count == 3:
        return "3-syl"
    else:
        return "4+-syl"


def variant_bucket(count: int) -> str:
    if count <= 5:
        return "low"
    elif count <= 30:
        return "medium"
    else:
        return "high"


def compute_coverage_stats(entries: list[dict], dictionary: dict) -> dict:
    """Compute component dictionary coverage across all entries.

    A component is "covered" if its g2p key exists in the dictionary
    (even if it maps to only one variant). A component is "unknown"
    only if the key is completely absent from the dictionary.
    """
    total_components = 0
    unknown_onsets: Counter = Counter()
    unknown_vowels: Counter = Counter()
    unknown_codas: Counter = Counter()
    all_onsets: Counter = Counter()
    all_vowels: Counter = Counter()
    all_codas: Counter = Counter()

    known_onsets = set(dictionary["onsets"].keys())
    known_vowels = set(dictionary["vowels"].keys())
    known_codas = set(dictionary["codas"].keys())

    # Zero-onset and empty coda are always valid (not dictionary entries)
    skip_onsets = {"?", ""}
    skip_codas = {""}

    for entry in entries:
        for comp in entry.get("components", []):
            total_components += 1
            onset = comp["onset"]
            vowel = comp["vowel"]
            coda = comp["coda"]

            all_onsets[onset] += 1
            all_vowels[vowel] += 1
            all_codas[coda] += 1

            if onset not in known_onsets and onset not in skip_onsets:
                unknown_onsets[onset] += 1
            if vowel not in known_vowels and vowel != "":
                unknown_vowels[vowel] += 1
            if coda not in known_codas and coda not in skip_codas:
                unknown_codas[coda] += 1

    unknown_count = sum(unknown_onsets.values()) + sum(unknown_vowels.values()) + sum(unknown_codas.values())
    coverage = 1.0 - (unknown_count / total_components) if total_components else 0.0

    return {
        "total_components": total_components,
        "coverage_pct": coverage * 100,
        "unknown_onsets": unknown_onsets,
        "unknown_vowels": unknown_vowels,
        "unknown_codas": unknown_codas,
        "unique_onsets": len(all_onsets),
        "unique_vowels": len(all_vowels),
        "unique_codas": len(all_codas),
    }


def main():
    parser = argparse.ArgumentParser(description="Stratified sample from 10K draft benchmark.")
    parser.add_argument("--input", type=str, default=None, help="Input draft_benchmark.json")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--sample-size", type=int, default=300, help="Target sample size (default: 300)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else DEFAULT_INPUT
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]
    failed = data.get("failed", [])

    print(f"Loaded {len(entries)} entries ({len(failed)} failed)")

    # Load the component dictionary for coverage checking
    sys.path.insert(0, str(REPO_ROOT))
    from src.variant_generator import load_component_dictionary
    dictionary = load_component_dictionary()

    # --- Coverage statistics ---
    coverage = compute_coverage_stats(entries, dictionary)
    print(f"\n{'=' * 60}")
    print("Component dictionary coverage")
    print(f"{'=' * 60}")
    print(f"  Total components: {coverage['total_components']}")
    print(f"  Coverage: {coverage['coverage_pct']:.1f}%")
    print(f"  Unique onsets: {coverage['unique_onsets']}, vowels: {coverage['unique_vowels']}, codas: {coverage['unique_codas']}")

    if coverage["unknown_onsets"]:
        print(f"\n  Unknown onsets ({sum(coverage['unknown_onsets'].values())} occurrences):")
        for k, v in coverage["unknown_onsets"].most_common(10):
            print(f"    {k!r}: {v}")
    if coverage["unknown_vowels"]:
        print(f"\n  Unknown vowels ({sum(coverage['unknown_vowels'].values())} occurrences):")
        for k, v in coverage["unknown_vowels"].most_common(10):
            print(f"    {k!r}: {v}")
    if coverage["unknown_codas"]:
        print(f"\n  Unknown codas ({sum(coverage['unknown_codas'].values())} occurrences):")
        for k, v in coverage["unknown_codas"].most_common(10):
            print(f"    {k!r}: {v}")

    # --- Stratified sampling ---
    print(f"\n{'=' * 60}")
    print("Stratified sampling")
    print(f"{'=' * 60}")

    # Assign strata
    strata: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for entry in entries:
        ft = frequency_tier(entry["frequency_rank"])
        sb = syllable_bucket(entry["syllable_count"])
        vb = variant_bucket(entry["variant_count"])
        strata[(ft, sb, vb)].append(entry)

    print(f"  {len(strata)} strata found")

    # Show stratum sizes
    for key in sorted(strata.keys()):
        print(f"    {key}: {len(strata[key])} words")

    # Sample proportionally, minimum 1 per non-empty stratum
    rng = random.Random(args.seed)
    target = args.sample_size
    total = len(entries)
    sampled: list[dict] = []

    for key in sorted(strata.keys()):
        pool = strata[key]
        # Proportional allocation, min 1, max pool size
        n = max(1, round(len(pool) / total * target))
        n = min(n, len(pool))
        sampled.extend(rng.sample(pool, n))

    # If we overshot, trim randomly; if under, add more from largest strata
    if len(sampled) > target:
        sampled = rng.sample(sampled, target)
    elif len(sampled) < target:
        remaining = [e for e in entries if e not in sampled]
        extra = rng.sample(remaining, min(target - len(sampled), len(remaining)))
        sampled.extend(extra)

    # Sort by frequency rank for easier review
    sampled.sort(key=lambda e: e["frequency_rank"])

    print(f"\n  Sampled {len(sampled)} words (target: {target})")

    # --- Write CSV ---
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rank", "thai_word", "syllable_count", "variant_count",
            "category", "difficulty", "decomposition",
            "rtgs_romanization", "variants",
        ])
        for entry in sampled:
            decomp = " | ".join(
                f"[{c['onset']}/{c['vowel']}/{c['coda']}]"
                for c in entry["components"]
            )
            writer.writerow([
                entry["frequency_rank"],
                entry["thai_word"],
                entry["syllable_count"],
                entry["variant_count"],
                entry["category"],
                entry["difficulty"],
                decomp,
                entry["rtgs_romanization"],
                "; ".join(entry["variants"][:50]),  # Cap at 50 for readability
            ])

    print(f"\n  Written to: {output_path}")
    print(f"\n  Review columns: rank, thai_word, decomposition, rtgs, variants")
    print(f"  Mark each word as: OK / NOISE (implausible variants) / MISS (missing variants)")


if __name__ == "__main__":
    main()
