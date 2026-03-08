"""Spot-check: generate variants for top 50 words by frequency."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.variant_generator import analyze_word, generate_word_variants


def main():
    # Load top 50 from frequency list
    freq_path = REPO_ROOT / "pipelines" / "benchmark-wordconv" / "output" / "word_frequencies.csv"
    with open(freq_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        words = [(row["rank"], row["thai_word"]) for row in reader][:50]

    # Generate and write CSV
    out_path = REPO_ROOT / "experiments" / "top50_variants.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "thai_word", "decomposition", "variant_count", "variants"])

        for rank, thai in words:
            syllables = analyze_word(thai)
            decomp = " | ".join(
                f"[{c.onset}/{c.vowel}/{c.coda}]" for c in syllables
            )
            variants = generate_word_variants(thai, max_variants=200)
            writer.writerow([rank, thai, decomp, len(variants), "; ".join(variants)])

            # Also print for quick terminal review
            print(f"{rank:>3}. {thai}  ({decomp})  [{len(variants)} variants]")
            # Show variants in rows of ~8
            for i in range(0, len(variants), 8):
                chunk = variants[i:i+8]
                print(f"     {', '.join(chunk)}")
            print()

    print(f"CSV written to: {out_path}")


if __name__ == "__main__":
    main()
