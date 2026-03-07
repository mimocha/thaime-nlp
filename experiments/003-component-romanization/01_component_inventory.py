"""Stage 1: Component Inventory — Extract all distinct phonological components.

Runs TLTK's analyze_word() on the top-k most frequent Thai words and extracts
all unique onsets, vowels, and codas. Outputs a summary table and detailed
per-word decomposition for manual review.

Usage:
    python -m experiments.003-component-romanization.01_component_inventory
    python -m experiments.003-component-romanization.01_component_inventory --top-k 500
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from src.variant_generator import analyze_word

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FREQ_CSV = REPO_ROOT / "pipelines" / "benchmark-wordconv" / "output" / "word_frequencies.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def load_top_words(path: Path, top_k: int) -> list[str]:
    """Load top-k Thai words from the frequency CSV."""
    words = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append(row["thai_word"])
            if len(words) >= top_k:
                break
    return words


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract component inventory from top Thai words.")
    parser.add_argument("--top-k", type=int, default=1000, help="Number of top words to analyze (default: 1000)")
    args = parser.parse_args()

    if not FREQ_CSV.exists():
        print(f"ERROR: Word frequency file not found: {FREQ_CSV}")
        print("Run: python -m pipelines.benchmark-wordconv.01_extract_frequencies --top-k 1000")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load words
    words = load_top_words(FREQ_CSV, args.top_k)
    print(f"Loaded {len(words)} words from {FREQ_CSV.name}")

    # Analyze each word
    onset_counter: Counter[str] = Counter()
    vowel_counter: Counter[str] = Counter()
    coda_counter: Counter[str] = Counter()

    decomposition_rows: list[dict] = []
    failed_words: list[str] = []

    for word in words:
        syllables = analyze_word(word)
        if not syllables:
            failed_words.append(word)
            continue

        for syl in syllables:
            onset = syl.initial_cluster or "(none)"
            vowel = syl.vowel_nucleus or "(none)"
            coda = syl.final_consonant or "(none)"

            onset_counter[onset] += 1
            vowel_counter[vowel] += 1
            coda_counter[coda] += 1

            decomposition_rows.append({
                "word": word,
                "syllable_thai": syl.thai_text,
                "syllable_roman": syl.romanization,
                "onset": syl.initial_cluster,
                "vowel": syl.vowel_nucleus,
                "coda": syl.final_consonant,
                "has_long_vowel": syl.has_long_vowel,
                "ipa": syl.ipa,
                "g2p": syl.g2p_group,
            })

    # Print summary
    print(f"\nAnalyzed {len(words)} words → {len(decomposition_rows)} syllables")
    print(f"Failed words (no TLTK output): {len(failed_words)}")

    print(f"\n{'='*60}")
    print(f"ONSETS: {len(onset_counter)} unique")
    print(f"{'='*60}")
    for onset, count in onset_counter.most_common():
        print(f"  {onset:>8s}  {count:5d}")

    print(f"\n{'='*60}")
    print(f"VOWELS: {len(vowel_counter)} unique")
    print(f"{'='*60}")
    for vowel, count in vowel_counter.most_common():
        print(f"  {vowel:>8s}  {count:5d}")

    print(f"\n{'='*60}")
    print(f"CODAS: {len(coda_counter)} unique")
    print(f"{'='*60}")
    for coda, count in coda_counter.most_common():
        print(f"  {coda:>8s}  {count:5d}")

    total = len(onset_counter) + len(vowel_counter) + len(coda_counter)
    print(f"\nTotal unique components: {total}")

    # Write detailed decomposition CSV
    decomp_path = OUTPUT_DIR / "syllable_decomposition.csv"
    with open(decomp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "word", "syllable_thai", "syllable_roman",
            "onset", "vowel", "coda",
            "has_long_vowel", "ipa", "g2p",
        ])
        writer.writeheader()
        writer.writerows(decomposition_rows)
    print(f"\nDecomposition written to: {decomp_path}")

    # Write inventory summary CSV
    inventory_path = OUTPUT_DIR / "component_inventory.csv"
    with open(inventory_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["component_type", "component", "count"])
        for onset, count in onset_counter.most_common():
            writer.writerow(["onset", onset, count])
        for vowel, count in vowel_counter.most_common():
            writer.writerow(["vowel", vowel, count])
        for coda, count in coda_counter.most_common():
            writer.writerow(["coda", coda, count])
    print(f"Inventory written to: {inventory_path}")

    # Write failed words
    if failed_words:
        failed_path = OUTPUT_DIR / "failed_words.txt"
        with open(failed_path, "w", encoding="utf-8") as f:
            for w in failed_words:
                f.write(w + "\n")
        print(f"Failed words written to: {failed_path}")


if __name__ == "__main__":
    main()
