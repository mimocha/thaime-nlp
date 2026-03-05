"""Generate the seed benchmark dataset from evaluation results.

Combines TLTK base romanizations with curated variant generator output
into structured (Thai word, accepted romanizations) entries.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from test_words import TEST_WORDS
from variant_generator import DEFAULT_CONFIG, generate_word_variants


def generate_seed_benchmark() -> list[dict]:
    """Generate seed benchmark entries for the word-conversion benchmark.

    Each entry contains:
    - thai: the Thai word
    - accepted_romanizations: list of accepted romanization forms
    - category: word category from the test set
    - source: how the romanizations were generated
    """
    entries = []

    for word_entry in TEST_WORDS:
        thai = word_entry["thai"]
        category = word_entry["category"]
        expected = set(word_entry["expected_informal"])

        # Generate variants from the variant generator
        generated = set(generate_word_variants(thai, DEFAULT_CONFIG))

        # Combine: all expected informal forms + all generated variants
        # For the seed benchmark, we include everything — the maintainer
        # will review and curate
        all_romanizations = sorted(expected | generated)

        entries.append({
            "thai": thai,
            "accepted_romanizations": all_romanizations,
            "category": category,
            "source": "task-002-generated",
            "notes": {
                "from_expected": sorted(expected),
                "from_generator": sorted(generated),
                "overlap": sorted(expected & generated),
            },
        })

    return entries


if __name__ == "__main__":
    entries = generate_seed_benchmark()

    output_path = Path(__file__).parent.parent / "data" / "seed-benchmark.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(entries)} seed benchmark entries → {output_path}")

    # Print summary stats
    total_romans = sum(len(e["accepted_romanizations"]) for e in entries)
    avg_romans = total_romans / len(entries)
    print(f"Total romanizations: {total_romans}")
    print(f"Average per word: {avg_romans:.1f}")
