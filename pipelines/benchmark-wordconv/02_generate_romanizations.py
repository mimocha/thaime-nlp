"""Step 2: Generate romanization variants for top-K Thai words.

Takes the word frequency list from Step 1, runs TLTK romanization +
the variant generator on each word, auto-assigns categories and difficulty,
and outputs a draft dataset ready for manual review.

Output: pipelines/benchmark-wordconv/output/draft_benchmark.json

Usage:
    python -m pipelines.benchmark-wordconv.02_generate_romanizations
    python -m pipelines.benchmark-wordconv.02_generate_romanizations --top-k 300
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Add repo root to path so we can import src modules
sys.path.insert(0, str(REPO_ROOT))

from src.variant_generator import (
    VariantConfig,
    analyze_word,
    generate_word_variants,
    _clean_tltk_output,
)

import tltk

# ---------------------------------------------------------------------------
# Category / difficulty heuristics
# ---------------------------------------------------------------------------

# Common function words and particles
_FUNCTION_WORDS = {
    "ที่", "ของ", "ใน", "ได้", "ไม่", "มี", "เป็น", "จะ", "ว่า", "ก็",
    "แต่", "กับ", "ให้", "ไป", "มา", "จาก", "หรือ", "ถ้า", "เพราะ", "ต้อง",
    "คือ", "อยู่", "แล้ว", "ยัง", "ทั้ง", "อย่าง", "ดี", "มาก", "น่า", "ครับ",
    "ค่ะ", "นะ", "คะ", "จ้า", "เลย", "นี้", "นั้น", "ซึ่ง", "เมื่อ", "โดย",
    "กัน", "คน", "วัน", "ปี", "ตอน", "ทำ", "ดู", "รู้", "พูด", "คิด",
    "เรา", "เขา", "ผม", "ฉัน", "ตัว", "หน้า", "ใจ", "ตา", "มือ", "หัว",
}

# Words that commonly have ambiguous romanizations (map to multiple Thai words)
_KNOWN_AMBIGUOUS_ROMANIZATIONS = {
    "ไม", "ไม่", "ไม้", "ไหม", "ไหม้", "ใหม่",  # mai
    "เกา", "เก่า", "เก้า", "เขา", "เข่า", "เข้า", "ขาว", "ข่าว", "ข้าว", "เค้า", "คาว",  # kao/khao
    "กัน", "กรรณ", "คัน", "คั่น", "คั้น", "ขัน", "ขั้น",   # kan
    "ตา", "ต่า", "ตาร์", "ทา", "ท่า", "ท้า", "ถ้า",  # ta
    "ดิ", "ดี", "ติ", "ตี", "ตี่", "ตี้", "ตี๋",  # di/dee
    "สิ", "สี", "สี่", "สี้", "ซิ", "ซี", "ซี้", "ศรี",  # si/sri
    "ใน", "ไหน", "นัย",  # nai
    "ชะ", "ช่ะ", "ชา", "ช่า", "ช้า", "ฉา", "ฉ่า",  # cha
}


def _count_syllables(thai_word: str) -> int:
    """Estimate syllable count using TLTK."""
    try:
        syl_raw = tltk.nlp.syl_segment(thai_word)
        cleaned = re.sub(r"<[^>]+>", "", syl_raw).strip()
        syllables = [s for s in cleaned.split("~") if s]
        return max(1, len(syllables))
    except Exception:
        return max(1, len(thai_word) // 3)


def _has_cluster(romanization: str) -> bool:
    """Check if romanization starts with a consonant cluster."""
    clusters = ["kh", "th", "ph", "ch", "kr", "tr", "pr", "kl", "pl", "bl", "fr", "fl"]
    rom_lower = romanization.lower()
    return any(rom_lower.startswith(c) for c in clusters)


def classify_word(
    thai_word: str,
    romanization: str,
    variant_count: int,
    merged_rank: int,
    syllable_count: int,
) -> tuple[str, str]:
    """Auto-classify a word into category and difficulty.

    Returns:
        (category, difficulty) tuple.
    """
    # Category assignment
    if thai_word in _KNOWN_AMBIGUOUS_ROMANIZATIONS:
        category = "ambiguous"
    elif syllable_count >= 3:
        category = "compound"
    elif variant_count > 10:
        category = "variant"
    elif len(thai_word) <= 2 and syllable_count == 1:
        category = "edge"
    elif thai_word in _FUNCTION_WORDS and merged_rank <= 100:
        category = "common"
    elif merged_rank <= 200:
        category = "common"
    else:
        category = "common"

    # Difficulty assignment
    if syllable_count == 1 and not _has_cluster(romanization):
        difficulty = "easy"
    elif syllable_count <= 2 and variant_count <= 5:
        difficulty = "easy"
    elif syllable_count >= 3 or _has_cluster(romanization):
        difficulty = "medium"
    elif variant_count > 8:
        difficulty = "medium"
    else:
        difficulty = "easy"

    # Override to hard for genuinely tricky cases
    if syllable_count >= 4:
        difficulty = "hard"
    if thai_word in _KNOWN_AMBIGUOUS_ROMANIZATIONS and syllable_count >= 2:
        difficulty = "hard"

    return category, difficulty


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate romanization variants for top-K words."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input word frequencies CSV (default: output/word_frequencies.csv)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=500,
        help="Number of top words to process (default: 500)",
    )
    parser.add_argument(
        "--max-variants",
        type=int,
        default=20,
        help="Max variants per word (default: 20)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: output/draft_benchmark.json)",
    )
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else OUTPUT_DIR / "word_frequencies.csv"
    output_path = Path(args.output) if args.output else OUTPUT_DIR / "draft_benchmark.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read word frequency list
    print("=" * 60)
    print("Reading word frequency list")
    print("=" * 60)

    words: list[dict] = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append(row)
            if len(words) >= args.top_k:
                break

    print(f"  Loaded {len(words)} words from {input_path}")

    # Configure variant generator
    config = VariantConfig(max_variants_per_word=args.max_variants)

    # Process each word
    print(f"\n{'=' * 60}")
    print("Generating romanizations and variants")
    print("=" * 60)

    entries: list[dict] = []
    failed: list[dict] = []

    for i, word_data in enumerate(words):
        thai_word = word_data["thai_word"]
        rank = int(word_data["rank"])

        # Get TLTK base romanization
        try:
            base_roman = _clean_tltk_output(tltk.nlp.th2roman(thai_word))
        except Exception:
            base_roman = ""

        if not base_roman:
            failed.append({"thai_word": thai_word, "rank": rank, "reason": "TLTK empty"})
            continue

        # Generate variants
        variants = generate_word_variants(thai_word, config)

        # Analyze syllables
        syllable_count = _count_syllables(thai_word)

        # Classify
        category, difficulty = classify_word(
            thai_word=thai_word,
            romanization=base_roman,
            variant_count=len(variants),
            merged_rank=rank,
            syllable_count=syllable_count,
        )

        entry = {
            "thai_word": thai_word,
            "rtgs_romanization": base_roman,
            "variants": variants,
            "variant_count": len(variants),
            "category": category,
            "difficulty": difficulty,
            "syllable_count": syllable_count,
            "frequency_rank": rank,
            "corpus_count": int(word_data.get("corpus_count", 0)),
            "notes": "",
            "review_status": "pending",  # pending | approved | edited | discarded
        }
        entries.append(entry)

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(words)} words...")

    print(f"\n  Successfully processed: {len(entries)}")
    print(f"  Failed (TLTK errors): {len(failed)}")

    # Category distribution
    from collections import Counter
    cat_dist = Counter(e["category"] for e in entries)
    diff_dist = Counter(e["difficulty"] for e in entries)
    print(f"\n  Category distribution:")
    for cat, count in sorted(cat_dist.items()):
        print(f"    {cat}: {count}")
    print(f"\n  Difficulty distribution:")
    for diff, count in sorted(diff_dist.items()):
        print(f"    {diff}: {count}")

    # Write output
    output_data = {
        "metadata": {
            "version": "v0.1.0-draft",
            "source": "pipeline/benchmark-v1",
            "corpora": ["wisesight", "wongnai", "prachathai"],
            "weighting": "equal (1/3 each)",
            "top_k_input": args.top_k,
            "total_entries": len(entries),
            "total_failed": len(failed),
        },
        "entries": entries,
        "failed": failed,
    }

    print(f"\n  Writing to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  Done! {len(entries)} entries ready for review.")


if __name__ == "__main__":
    main()
