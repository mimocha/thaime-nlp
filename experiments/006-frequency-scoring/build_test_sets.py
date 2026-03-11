"""Build three evaluation test sets from the trie dataset.

Sets produced:
  A — Common word ranking (unambiguous inputs from top 2K)
  B — Ambiguous input discrimination (romanization collisions)
  C — Override list recall (cross-reference with overrides YAML)

Usage:
    python experiments/006-frequency-scoring/build_test_sets.py
"""

import json
import math
from collections import defaultdict
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
TRIE_PATH = SCRIPT_DIR / "reference" / "trie_dataset_sample_5k.json"
OVERRIDES_PATH = (
    SCRIPT_DIR.parent.parent / "data" / "dictionaries" / "word_overrides" / "overrides-v0.4.2.yaml"
)
OUTPUT_DIR = SCRIPT_DIR
# Fixed date for reproducibility — test sets should be regenerated deterministically
DATE = "2026-03-11"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_trie_dataset() -> dict:
    with open(TRIE_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_overrides() -> dict:
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def shortest_romanization(romanizations: list[str]) -> str:
    """Return the shortest romanization; break ties alphabetically."""
    return min(romanizations, key=lambda r: (len(r), r))


def evenly_spaced_sample(items: list, n: int) -> list:
    """Deterministic stride-based selection of *n* items from a sorted list."""
    if n >= len(items):
        return list(items)
    stride = len(items) / n
    return [items[int(i * stride)] for i in range(n)]


def save_json(obj: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  Saved → {path.relative_to(SCRIPT_DIR)}")


# ---------------------------------------------------------------------------
# Set A — Common Word Ranking
# ---------------------------------------------------------------------------

def build_set_a(entries: list[dict]) -> dict:
    # Sort by frequency descending, assign ranks
    sorted_entries = sorted(entries, key=lambda e: e["frequency"], reverse=True)
    for rank, entry in enumerate(sorted_entries, start=1):
        entry["_rank"] = rank

    top_2k = sorted_entries[:2000]

    # Map romanization → list of top-2K words that use it as their shortest
    rom_to_words: dict[str, list[dict]] = defaultdict(list)
    for entry in top_2k:
        shortest = shortest_romanization(entry["romanizations"])
        entry["_shortest_rom"] = shortest
        rom_to_words[shortest].append(entry)

    # Keep only unambiguous inputs (romanization maps to exactly one top-2K word)
    unambiguous = [
        entry for entry in top_2k if len(rom_to_words[entry["_shortest_rom"]]) == 1
    ]

    # Stratify into frequency bands
    bands = {
        "top_100": (1, 100),
        "100_500": (101, 500),
        "500_1000": (501, 1000),
        "1000_2000": (1001, 2000),
    }
    target_counts = {"top_100": 18, "100_500": 18, "500_1000": 18, "1000_2000": 16}

    band_entries: dict[str, list[dict]] = {band: [] for band in bands}
    for entry in unambiguous:
        for band, (lo, hi) in bands.items():
            if lo <= entry["_rank"] <= hi:
                band_entries[band].append(entry)
                break

    # Sort within each band by frequency (descending) and sample evenly
    sampled: list[dict] = []
    band_counts: dict[str, int] = {}
    for band, target in target_counts.items():
        pool = sorted(band_entries[band], key=lambda e: e["frequency"], reverse=True)
        chosen = evenly_spaced_sample(pool, target)
        band_counts[band] = len(chosen)
        for entry in chosen:
            sampled.append(
                {
                    "romanization_input": entry["_shortest_rom"],
                    "expected_thai": entry["thai"],
                    "word_id": entry["word_id"],
                    "frequency": entry["frequency"],
                    "rank": entry["_rank"],
                    "frequency_band": band,
                }
            )

    # Sort final output by rank
    sampled.sort(key=lambda e: e["rank"])

    return {
        "metadata": {
            "description": "Common word ranking test set",
            "source": "trie_dataset_sample_5k.json, top 2K by frequency, unambiguous inputs only",
            "size": len(sampled),
            "date": DATE,
            "frequency_bands": band_counts,
        },
        "entries": sampled,
    }


# ---------------------------------------------------------------------------
# Set B — Ambiguous Input Discrimination
# ---------------------------------------------------------------------------

def build_set_b(entries: list[dict]) -> dict:
    TARGET = 25

    # Build romanization → words mapping (all 5K entries, shortest rom)
    rom_to_words: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        shortest = shortest_romanization(entry["romanizations"])
        rom_to_words[shortest].append(entry)

    # Find collisions (2+ words sharing the same shortest romanization)
    collisions: list[dict] = []
    for rom, words in rom_to_words.items():
        if len(words) < 2:
            continue
        words_sorted = sorted(words, key=lambda w: w["frequency"], reverse=True)
        top = words_sorted[0]
        others = words_sorted[1:]
        second_freq = others[0]["frequency"]
        if second_freq == 0:
            ratio = float("inf")
        else:
            ratio = top["frequency"] / second_freq

        collisions.append(
            {
                "romanization_input": rom,
                "expected_top_candidate": top["thai"],
                "expected_top_word_id": top["word_id"],
                "expected_top_frequency": top["frequency"],
                "other_candidates": [
                    {"thai": w["thai"], "word_id": w["word_id"], "frequency": w["frequency"]}
                    for w in others
                ],
                "frequency_ratio": round(ratio, 2),
            }
        )

    # Prefer diverse frequency ratios: filter out inf, sort by ratio desc, sample evenly
    finite = [c for c in collisions if math.isfinite(c["frequency_ratio"])]
    # Also prefer ratios > 1 (meaningful discrimination)
    finite = [c for c in finite if c["frequency_ratio"] > 1.0]
    finite.sort(key=lambda c: c["frequency_ratio"], reverse=True)

    chosen = evenly_spaced_sample(finite, TARGET)
    # Sort final output by frequency ratio descending
    chosen.sort(key=lambda c: c["frequency_ratio"], reverse=True)

    return {
        "metadata": {
            "description": "Ambiguous input discrimination test set",
            "source": "trie_dataset_sample_5k.json collisions",
            "size": len(chosen),
            "date": DATE,
        },
        "entries": chosen,
    }


# ---------------------------------------------------------------------------
# Set C — Override List Recall
# ---------------------------------------------------------------------------

def build_set_c(entries: list[dict], overrides: dict) -> dict:
    thai_to_entry = {entry["thai"]: entry for entry in entries}

    result_entries: list[dict] = []
    in_trie_count = 0

    for thai_word, rom_list in sorted(overrides.items()):
        entry_data = thai_to_entry.get(thai_word)
        in_trie = entry_data is not None
        if in_trie:
            in_trie_count += 1

        rec: dict = {
            "thai": thai_word,
            "override_romanizations": rom_list,
            "in_trie": in_trie,
        }
        if in_trie:
            rec["word_id"] = entry_data["word_id"]
            rec["frequency"] = entry_data["frequency"]
        else:
            rec["word_id"] = None
            rec["frequency"] = None

        result_entries.append(rec)

    return {
        "metadata": {
            "description": "Override list recall test set",
            "source": "overrides-v0.4.2.yaml cross-referenced with trie_dataset_sample_5k.json",
            "size": len(result_entries),
            "total_overrides": len(overrides),
            "in_trie_count": in_trie_count,
            "date": DATE,
        },
        "entries": result_entries,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading trie dataset …")
    trie_data = load_trie_dataset()
    entries = trie_data["entries"]
    print(f"  {len(entries)} entries loaded")

    print("Loading overrides …")
    overrides = load_overrides()
    print(f"  {len(overrides)} override words loaded\n")

    # --- Set A ---
    print("Building Set A — Common Word Ranking …")
    set_a = build_set_a(entries)
    save_json(set_a, OUTPUT_DIR / "test_set_a.json")
    meta_a = set_a["metadata"]
    print(f"  Size: {meta_a['size']}")
    print(f"  Bands: {meta_a['frequency_bands']}\n")

    # --- Set B ---
    print("Building Set B — Ambiguous Input Discrimination …")
    set_b = build_set_b(entries)
    save_json(set_b, OUTPUT_DIR / "test_set_b.json")
    meta_b = set_b["metadata"]
    print(f"  Size: {meta_b['size']}")
    ratios = [e["frequency_ratio"] for e in set_b["entries"]]
    if ratios:
        print(f"  Ratio range: {min(ratios):.2f} – {max(ratios):.2f}\n")

    # --- Set C ---
    print("Building Set C — Override List Recall …")
    set_c = build_set_c(entries, overrides)
    save_json(set_c, OUTPUT_DIR / "test_set_c.json")
    meta_c = set_c["metadata"]
    print(f"  Size: {meta_c['size']}")
    print(f"  Total overrides: {meta_c['total_overrides']}")
    print(f"  In trie: {meta_c['in_trie_count']}\n")

    print("Done.")


if __name__ == "__main__":
    main()
