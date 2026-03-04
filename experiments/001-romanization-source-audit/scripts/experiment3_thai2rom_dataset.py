"""
Experiment 3: thai2rom-dataset Analysis

Downloads and analyzes the PyThaiNLP thai2rom-dataset (648K pairs, CC0 license).
Assesses coverage, quality, and usability for THAIME trie construction.
"""

import csv
import os
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
DATA_DIR = EXPERIMENT_DIR / "data"
DATASET_PATH = DATA_DIR / "thai2rom_dataset.csv"
DATASET_URL = "https://raw.githubusercontent.com/wannaphong/thai-romanization/master/dataset/data.csv"


def download_dataset():
    """Download the thai2rom-dataset if not already present."""
    if DATASET_PATH.exists():
        print(f"Dataset already exists at {DATASET_PATH}")
        return

    print(f"Downloading thai2rom-dataset from {DATASET_URL}...")
    import urllib.request

    urllib.request.urlretrieve(DATASET_URL, DATASET_PATH)
    print(f"Downloaded to {DATASET_PATH}")


def analyze_dataset():
    """Analyze the thai2rom-dataset."""
    print("=" * 80)
    print("THAI2ROM DATASET ANALYSIS")
    print("=" * 80)

    # Load dataset (tab-separated, no header)
    rows = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "\t" in line:
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    rows.append({"thai": parts[0], "romanization": parts[1]})

    print(f"\nFormat: tab-separated, no header")
    print(f"Total rows: {len(rows):,}")

    # Basic stats
    thai_words = [r["thai"] for r in rows]
    romanizations = [r["romanization"] for r in rows]
    unique_thai = set(thai_words)
    unique_roman = set(romanizations)

    print(f"Unique Thai words: {len(unique_thai):,}")
    print(f"Unique romanizations: {len(unique_roman):,}")

    # Romanization variants per Thai word
    thai_to_romans = {}
    for r in rows:
        thai_to_romans.setdefault(r["thai"], set()).add(r["romanization"])

    variants_per_word = [len(v) for v in thai_to_romans.values()]
    print(f"\nRomanization variants per Thai word:")
    print(f"  Mean: {sum(variants_per_word)/len(variants_per_word):.2f}")
    print(f"  Max: {max(variants_per_word)}")
    print(f"  1 variant: {sum(1 for v in variants_per_word if v == 1):,} words")
    print(
        f"  2+ variants: {sum(1 for v in variants_per_word if v >= 2):,} words"
    )
    print(
        f"  5+ variants: {sum(1 for v in variants_per_word if v >= 5):,} words"
    )

    # Word length distribution
    thai_lengths = [len(w) for w in unique_thai]
    print(f"\nThai word length distribution:")
    print(f"  Mean: {sum(thai_lengths)/len(thai_lengths):.1f} characters")
    print(f"  Min: {min(thai_lengths)}, Max: {max(thai_lengths)}")

    # Sample entries
    print("\n--- Sample entries (first 20) ---")
    print(f"{'Thai':<20} {'Romanization':<30}")
    print("-" * 50)
    for r in rows[:20]:
        print(f"{r['thai']:<20} {r['romanization']:<30}")

    # Check overlap with our sample words
    sample_path = DATA_DIR / "sample_words.csv"
    if sample_path.exists():
        with open(sample_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            sample_words = [r["thai"] for r in reader]

        found = 0
        print(f"\n--- Overlap with sample word set ({len(sample_words)} words) ---")
        for word in sample_words:
            if word in thai_to_romans:
                variants = thai_to_romans[word]
                found += 1
                if found <= 15:  # Show first 15
                    print(f"  {word}: {', '.join(sorted(variants))}")
            else:
                print(f"  {word}: NOT FOUND")

        print(f"\nOverlap: {found}/{len(sample_words)} sample words found in dataset")

    # Words with most romanization variants
    print("\n--- Words with most romanization variants ---")
    by_variants = sorted(thai_to_romans.items(), key=lambda x: len(x[1]), reverse=True)
    for thai, romans in by_variants[:10]:
        print(f"  {thai}: {len(romans)} variants - {', '.join(sorted(romans)[:5])}{'...' if len(romans) > 5 else ''}")

    # Save summary stats
    stats = {
        "total_rows": len(rows),
        "unique_thai": len(unique_thai),
        "unique_romanizations": len(unique_roman),
        "mean_variants_per_word": sum(variants_per_word) / len(variants_per_word),
        "max_variants_per_word": max(variants_per_word),
        "single_variant_words": sum(1 for v in variants_per_word if v == 1),
        "multi_variant_words": sum(1 for v in variants_per_word if v >= 2),
    }

    import json

    stats_path = DATA_DIR / "experiment3_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nStats saved to {stats_path}")


if __name__ == "__main__":
    download_dataset()
    analyze_dataset()
