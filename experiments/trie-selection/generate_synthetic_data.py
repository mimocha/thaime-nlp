"""Generate synthetic romanization dataset for trie benchmarking.

Produces (romanization_key, thai_word_id, confidence_weight) tuples that
match the expected shape of the real THAIME dictionary:
- 10K–30K Thai words × 3–5 romanization variants each
- Key lengths of 3–20 ASCII characters
- Total ~50K–100K keys

The exact romanizations do NOT need to be linguistically accurate.
What matters is the distribution of key lengths, multiplicity, and
total key count — these are what affect trie performance.

Usage:
    python generate_synthetic_data.py [--num-words N] [--output PATH]
"""

import argparse
import csv
import hashlib
import random
import string
from pathlib import Path


def generate_base_romanization(word_id: int, seed_str: str) -> str:
    """Generate a base romanization key from a seed string.

    Uses a deterministic hash to produce a plausible-looking ASCII key
    of length 3–15 characters.
    """
    h = hashlib.md5(seed_str.encode()).hexdigest()
    # Use hash to determine length (3-15) and characters
    length = 3 + (int(h[:2], 16) % 13)  # 3 to 15 chars
    # Build a consonant-vowel pattern for realistic romanization look
    consonants = "bcdfghjklmnpqrstvwxyz"
    vowels = "aeiou"
    result = []
    for i in range(length):
        pool = consonants if i % 2 == 0 else vowels
        idx = int(h[(i * 2) % len(h) : (i * 2 + 2) % len(h) or len(h)], 16)
        result.append(pool[idx % len(pool)])
    return "".join(result)


def generate_variants(base_key: str, num_variants: int, rng: random.Random) -> list[str]:
    """Generate romanization variants from a base key.

    Applies simple transformations to simulate the multi-romanization
    property (vowel substitutions, consonant alternatives, length changes).
    """
    variants = [base_key]
    vowel_subs = {
        "a": ["aa", "ah"],
        "e": ["ee", "eh", "ae"],
        "i": ["ii", "ee", "y"],
        "o": ["oo", "oh", "or"],
        "u": ["uu", "oo"],
    }
    consonant_subs = {
        "k": ["kh", "g"],
        "t": ["th", "d"],
        "p": ["ph", "b"],
        "c": ["ch", "j"],
        "s": ["sh", "z"],
    }

    attempts = 0
    while len(variants) < num_variants and attempts < num_variants * 5:
        attempts += 1
        v = list(base_key)
        # Apply 1-2 random transformations
        num_transforms = rng.randint(1, 2)
        for _ in range(num_transforms):
            pos = rng.randint(0, len(v) - 1)
            ch = v[pos]
            if ch in vowel_subs and rng.random() < 0.6:
                v[pos] = rng.choice(vowel_subs[ch])
            elif ch in consonant_subs and rng.random() < 0.4:
                v[pos] = rng.choice(consonant_subs[ch])
        new_variant = "".join(v)
        if new_variant not in variants and 3 <= len(new_variant) <= 20:
            variants.append(new_variant)

    return variants[:num_variants]


def generate_synthetic_dataset(
    num_words: int = 20000,
    min_variants: int = 3,
    max_variants: int = 5,
    seed: int = 42,
) -> list[tuple[str, int, float]]:
    """Generate a synthetic romanization dataset.

    Args:
        num_words: Number of Thai words to simulate.
        min_variants: Minimum romanization variants per word.
        max_variants: Maximum romanization variants per word.
        seed: Random seed for reproducibility.

    Returns:
        List of (romanization_key, word_id, confidence) tuples.
    """
    rng = random.Random(seed)
    dataset = []

    for word_id in range(num_words):
        # Generate a base romanization for this word
        base_key = generate_base_romanization(word_id, f"word_{word_id}_{seed}")

        # Decide number of variants for this word
        num_variants = rng.randint(min_variants, max_variants)

        # Generate variants
        variants = generate_variants(base_key, num_variants, rng)

        # Assign decreasing confidence weights
        for i, variant in enumerate(variants):
            confidence = round(1.0 / (i + 1), 3)  # 1.0, 0.5, 0.333, 0.25, 0.2
            dataset.append((variant, word_id, confidence))

    return dataset


def save_dataset(dataset: list[tuple[str, int, float]], output_path: Path) -> None:
    """Save dataset as TSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["romanization_key", "word_id", "confidence"])
        for key, word_id, confidence in dataset:
            writer.writerow([key, word_id, confidence])


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic romanization dataset for trie benchmarking."
    )
    parser.add_argument(
        "--num-words",
        type=int,
        default=20000,
        help="Number of Thai words to simulate (default: 20000)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: experiments/trie-selection/data/)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).resolve().parent / "data"

    # Generate datasets at three scale points
    scale_points = {
        "10k": 2500,   # ~2500 words × ~4 variants ≈ 10K keys
        "50k": 12500,  # ~12500 words × ~4 variants ≈ 50K keys
        "100k": 25000, # ~25000 words × ~4 variants ≈ 100K keys
    }

    for label, num_words in scale_points.items():
        print(f"\nGenerating {label} dataset ({num_words} words)...")
        dataset = generate_synthetic_dataset(
            num_words=num_words,
            seed=args.seed,
        )
        output_path = output_dir / f"synthetic_{label}.tsv"
        save_dataset(dataset, output_path)
        print(f"  → {len(dataset)} keys saved to {output_path}")

        # Print key length distribution
        key_lengths = [len(key) for key, _, _ in dataset]
        avg_len = sum(key_lengths) / len(key_lengths)
        print(f"  → Key length: min={min(key_lengths)}, max={max(key_lengths)}, avg={avg_len:.1f}")
        print(f"  → Unique keys: {len(set(key for key, _, _ in dataset))}")


if __name__ == "__main__":
    main()
