"""Stage 1b: Prepare component inventory for manual curation.

Reads the syllable decomposition CSV and produces per-component-type
curation CSVs with example words and romanizations for human review.

Usage:
    python -m experiments.003-component-romanization.02_prepare_curation
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DECOMP_CSV = OUTPUT_DIR / "syllable_decomposition.csv"

# Max example entries to show per component
MAX_EXAMPLES = 5


def load_decomposition() -> list[dict]:
    with open(DECOMP_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_component_table(
    rows: list[dict],
    component_key: str,
) -> list[dict]:
    """Group rows by component value and collect examples.

    Returns a list of dicts sorted by descending frequency, each with:
    - component: the component string
    - count: number of syllables with this component
    - examples: semicolon-separated "thai_syllable=romanization (word)" strings
    - valid: empty column for human annotation
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        val = row[component_key] or "(none)"
        groups[val].append(row)

    table = []
    for comp, group_rows in sorted(groups.items(), key=lambda x: -len(x[1])):
        # Pick diverse examples: prefer unique words
        seen_words: set[str] = set()
        examples = []
        for r in group_rows:
            if r["word"] not in seen_words and len(examples) < MAX_EXAMPLES:
                seen_words.add(r["word"])
                examples.append(r)

        example_strs = [
            f'{r["syllable_thai"]}={r["syllable_roman"]} ({r["word"]})'
            for r in examples
        ]

        table.append({
            "component": comp,
            "count": len(group_rows),
            "examples": "; ".join(example_strs),
            "valid": "",
        })

    return table


def write_table(table: list[dict], path: Path, component_label: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "component", "count", "examples", "valid",
        ])
        writer.writeheader()
        writer.writerows(table)
    print(f"  {component_label}: {len(table)} entries → {path.name}")


def main() -> None:
    rows = load_decomposition()
    print(f"Loaded {len(rows)} syllable rows\n")

    for component_key, label, filename in [
        ("onset", "Onsets", "curation_onsets.csv"),
        ("vowel", "Vowels", "curation_vowels.csv"),
        ("coda", "Codas", "curation_codas.csv"),
    ]:
        table = build_component_table(rows, component_key)
        write_table(table, OUTPUT_DIR / filename, label)


if __name__ == "__main__":
    main()
