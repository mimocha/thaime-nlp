"""Find romanization collisions in the trie dataset.

A "collision" is a romanization key that maps to multiple Thai words.
These are the ambiguous inputs that need context to disambiguate —
exactly the cases the ranking benchmark should cover.
"""

import json
import sys
from collections import defaultdict

def main():
    with open("pipelines/trie/outputs/trie_dataset.json", "r") as f:
        data = json.load(f)

    # Build reverse map: romanization -> list of (thai, frequency, word_id)
    rom_to_words = defaultdict(list)
    for entry in data["entries"]:
        for rom in entry["romanizations"]:
            rom_to_words[rom].append({
                "thai": entry["thai"],
                "frequency": entry["frequency"],
                "word_id": entry["word_id"],
            })

    # Filter to collisions (2+ words per romanization)
    collisions = {k: v for k, v in rom_to_words.items() if len(v) >= 2}

    # Sort collisions by number of candidates (most ambiguous first)
    sorted_collisions = sorted(collisions.items(), key=lambda x: (-len(x[1]), x[0]))

    print(f"Total unique romanization keys: {len(rom_to_words)}")
    print(f"Keys with collisions (2+ words): {len(collisions)}")
    print(f"Keys with 3+ words: {sum(1 for v in collisions.values() if len(v) >= 3)}")
    print(f"Keys with 5+ words: {sum(1 for v in collisions.values() if len(v) >= 5)}")
    print()

    # Show top collisions
    print("=" * 80)
    print("TOP 50 COLLISIONS (by number of candidates)")
    print("=" * 80)
    for rom, words in sorted_collisions[:50]:
        words_sorted = sorted(words, key=lambda w: -w["frequency"])
        candidates = "  ".join(
            f"{w['thai']}({w['frequency']:.6f})" for w in words_sorted
        )
        print(f"\n{rom} ({len(words)} candidates):")
        print(f"  {candidates}")

    # Also output all collisions as JSON for further analysis
    collision_data = {}
    for rom, words in sorted_collisions:
        collision_data[rom] = sorted(words, key=lambda w: -w["frequency"])

    with open("experiments/007-bigram-scoring/data/collisions.json", "w") as f:
        json.dump(collision_data, f, ensure_ascii=False, indent=2)
    print(f"\nFull collision data written to experiments/007-bigram-scoring/data/collisions.json")

    # Print some statistics about frequency gaps
    print("\n" + "=" * 80)
    print("COLLISION FREQUENCY ANALYSIS")
    print("=" * 80)
    tight_races = []
    for rom, words in sorted_collisions:
        words_sorted = sorted(words, key=lambda w: -w["frequency"])
        if len(words_sorted) >= 2:
            top = words_sorted[0]["frequency"]
            second = words_sorted[1]["frequency"]
            if top > 0:
                ratio = second / top
                if ratio > 0.3:  # Second candidate is within 70% of first
                    tight_races.append((rom, words_sorted, ratio))

    tight_races.sort(key=lambda x: -x[2])
    print(f"\nTight races (2nd candidate >= 30% of 1st): {len(tight_races)}")
    print("\nTop 30 tightest races (most context-dependent):")
    for rom, words, ratio in tight_races[:30]:
        top2 = f"{words[0]['thai']}({words[0]['frequency']:.6f}) vs {words[1]['thai']}({words[1]['frequency']:.6f})"
        print(f"  {rom}: {top2}  ratio={ratio:.3f}")


if __name__ == "__main__":
    main()
