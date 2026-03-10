"""
Romanization sanity-check heuristic analysis.

Generates CSV files for each heuristic so results can be reviewed manually.
All outputs are filtered to the agreed baseline: sources >= 2 (or pythainlp-only) AND freq >= 5e-6.

Usage:
    python pipelines/trie/heuristic_analysis.py
"""

import csv
import json
import re
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "outputs" / "heuristics"

# --- Thai character patterns ---
CONSONANTS = re.compile(r"[\u0E01-\u0E2E]")
VOWELS = re.compile(r"[\u0E30-\u0E39\u0E40-\u0E44\u0E47\u0E33]")
THANTHAKHAT = re.compile(r"\u0E4C")


def load_filtered_dataset(path: str) -> list[dict]:
    """Load trie dataset and apply baseline filters."""
    data = json.load(open(path))
    filtered = []
    for e in data["entries"]:
        srcs = e["sources"]
        freq = e["frequency"]
        if (len(srcs) >= 2 or srcs == ["pythainlp"]) and freq >= 5e-6:
            filtered.append(e)
    filtered.sort(key=lambda x: -x["frequency"])
    return filtered


# --- Heuristic helpers ---

def count_vowel_nuclei(word: str) -> int:
    """Estimate syllable count from Thai vowel characters."""
    all_vowels = len(VOWELS.findall(word))
    # Subtract common vowel pairs that form a single nucleus
    double = len(re.findall(r"\u0E40.\u0E47", word))  # เ-็
    double += len(re.findall(r"\u0E40.\u0E32", word))  # เ-า
    double += len(re.findall(r"\u0E40.\u0E35\u0E22", word))  # เ-ีย
    return max(1, all_vowels - double)


def count_rom_vowel_clusters(rom: str) -> int:
    """Count vowel clusters in a romanization string."""
    return max(1, len(re.findall(r"[aeiouy]+", rom, re.I)))


def longest_rom(roms: list[str]) -> str:
    return max(roms, key=len) if roms else ""


def shortest_rom(roms: list[str]) -> str:
    return min(roms, key=len) if roms else ""


def thai_base_len(word: str) -> int:
    """Count Thai chars excluding tone marks and thanthakhat."""
    return len(re.findall(r"[\u0E01-\u0E39\u0E40-\u0E44\u0E47\u0E33]", word))


# --- CSV writers ---

def write_csv(path: Path, headers: list[str], rows: list[list]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  {path.name}: {len(rows)} rows")


def run_h1_vowel_discrepancy(entries: list[dict]):
    """H1: thai_vowel_nuclei - rom_syllable_count."""
    headers = [
        "thai", "frequency", "source_count", "sources",
        "thai_vowel_nuclei", "rom_syllables", "discrepancy",
        "max_romanization", "romanizations",
    ]
    rows = []
    for e in entries:
        rom = longest_rom(e["romanizations"])
        thai_v = count_vowel_nuclei(e["thai"])
        rom_s = count_rom_vowel_clusters(rom) if rom else 0
        disc = thai_v - rom_s
        if disc >= 1:
            rows.append([
                e["thai"], f"{e['frequency']:.10f}", len(e["sources"]),
                "|".join(e["sources"]),
                thai_v, rom_s, disc,
                rom, "|".join(e["romanizations"]),
            ])
    write_csv(OUTPUT_DIR / "h1_vowel_discrepancy.csv", headers, rows)


def run_h2_consonant_discrepancy(entries: list[dict]):
    """H2: thai_consonants - rom_consonants - thanthakhat_count."""
    headers = [
        "thai", "frequency", "source_count", "sources",
        "thai_consonants", "rom_consonants", "thanthakhat", "discrepancy",
        "max_romanization", "romanizations",
    ]
    rows = []
    for e in entries:
        rom = longest_rom(e["romanizations"])
        th_c = len(CONSONANTS.findall(e["thai"]))
        rm_c = len(re.findall(r"[^aeiouy\s]", rom, re.I)) if rom else 0
        than = len(THANTHAKHAT.findall(e["thai"]))
        disc = th_c - rm_c - than
        if disc >= 2:
            rows.append([
                e["thai"], f"{e['frequency']:.10f}", len(e["sources"]),
                "|".join(e["sources"]),
                th_c, rm_c, than, disc,
                rom, "|".join(e["romanizations"]),
            ])
    write_csv(OUTPUT_DIR / "h2_consonant_discrepancy.csv", headers, rows)


def run_h3_length_ratio(entries: list[dict]):
    """H3: thai_base_chars / min_rom_length."""
    headers = [
        "thai", "frequency", "source_count", "sources",
        "thai_base_len", "min_rom_len", "length_ratio",
        "min_romanization", "romanizations",
    ]
    rows = []
    for e in entries:
        rom = shortest_rom(e["romanizations"])
        base = thai_base_len(e["thai"])
        rom_len = len(rom)
        ratio = base / rom_len if rom_len > 0 else 999.0
        if ratio > 2.0:
            rows.append([
                e["thai"], f"{e['frequency']:.10f}", len(e["sources"]),
                "|".join(e["sources"]),
                base, rom_len, f"{ratio:.2f}",
                rom, "|".join(e["romanizations"]),
            ])
    # Sort by ratio descending (highest discrepancy first)
    rows.sort(key=lambda r: -float(r[6]))
    write_csv(OUTPUT_DIR / "h3_length_ratio.csv", headers, rows)


def run_h4_absolute_floor(entries: list[dict]):
    """H4: thai_consonants vs max_rom_length (absolute thresholds)."""
    headers = [
        "thai", "frequency", "source_count", "sources",
        "thai_consonants", "max_rom_len",
        "max_romanization", "romanizations",
    ]
    rows = []
    for e in entries:
        rom = longest_rom(e["romanizations"])
        th_c = len(CONSONANTS.findall(e["thai"]))
        rom_len = len(rom)
        # Include all words with 3+ consonants and short romanization,
        # so reviewers can evaluate different threshold combos
        if th_c >= 3 and rom_len <= 5:
            rows.append([
                e["thai"], f"{e['frequency']:.10f}", len(e["sources"]),
                "|".join(e["sources"]),
                th_c, rom_len,
                rom, "|".join(e["romanizations"]),
            ])
    write_csv(OUTPUT_DIR / "h4_absolute_floor.csv", headers, rows)


def main():
    dataset_path = Path(__file__).parent / "outputs" / "trie_dataset.json"
    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Loading dataset from {dataset_path}...")
    entries = load_filtered_dataset(str(dataset_path))
    print(f"Filtered vocab: {len(entries)} words")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    print("Generating heuristic CSVs...")
    run_h1_vowel_discrepancy(entries)
    run_h2_consonant_discrepancy(entries)
    run_h3_length_ratio(entries)
    run_h4_absolute_floor(entries)
    print("\nDone.")


if __name__ == "__main__":
    main()
