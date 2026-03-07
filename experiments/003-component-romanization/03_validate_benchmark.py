"""Stage 3: Validate component dictionary against the v0.1.0 benchmark.

Decomposes each benchmark word into syllables via TLTK, looks up components
in the dictionary, generates variants via Cartesian product, and measures
how well the dictionary reproduces the benchmark's latin_input entries.

Falls back to raw TLTK romanization when a component is not found in the
dictionary (i.e., garbage decomposition from analyze_word bugs).

Usage:
    python -m experiments.003-component-romanization.03_validate_benchmark
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path

import yaml

from src.variant_generator import analyze_word, _clean_tltk_output

try:
    import tltk
except ImportError as e:
    raise ImportError("TLTK is required. Install with: pip install tltk") from e

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DICT_PATH = REPO_ROOT / "data" / "dictionaries" / "component-romanization.yaml"
BENCHMARK_PATH = REPO_ROOT / "benchmarks" / "word-conversion" / "v0.1.0.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def load_dictionary(path: Path) -> dict:
    """Load the component romanization dictionary."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_benchmark(path: Path) -> dict[str, set[str]]:
    """Load benchmark as {thai_word: set of valid latin_inputs}."""
    result: dict[str, set[str]] = defaultdict(set)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["expected_thai"]].add(row["latin_input"])
    return dict(result)


def get_component_variants(
    component_type: str,
    component_value: str,
    dictionary: dict,
) -> list[str] | None:
    """Look up variants for a component in the dictionary.

    Returns None if the component is not found (signals fallback).
    """
    section = dictionary.get(component_type, {})
    entry = section.get(component_value)
    if entry is None:
        return None
    return entry["variants"]


def generate_variants_from_dict(
    thai_word: str,
    dictionary: dict,
) -> tuple[list[str], list[dict]]:
    """Generate romanization variants for a Thai word using the dictionary.

    Returns:
        (variants, diagnostics) where:
        - variants: list of generated romanization strings
        - diagnostics: per-syllable diagnostic info for reporting
    """
    syllables = analyze_word(thai_word)
    diagnostics: list[dict] = []

    if not syllables:
        # TLTK failed entirely — fall back to raw romanization
        try:
            base = _clean_tltk_output(tltk.nlp.th2roman(thai_word))
        except Exception:
            return [], []
        if not base:
            return [], []
        diagnostics.append({
            "syllable": thai_word,
            "status": "tltk_failed",
            "onset": "", "vowel": "", "coda": "",
        })
        return [base], diagnostics

    syllable_options: list[list[str]] = []
    all_found = True

    for syl in syllables:
        onset_key = syl.initial_cluster or ""
        vowel_key = syl.vowel_nucleus or ""
        coda_key = syl.final_consonant or ""

        # Look up each component
        onset_variants = get_component_variants("onsets", onset_key, dictionary) if onset_key else [""]
        vowel_variants = get_component_variants("vowels", vowel_key, dictionary) if vowel_key else [""]
        coda_variants = get_component_variants("codas", coda_key, dictionary) if coda_key else [""]

        status = "ok"
        missing = []
        if onset_key and onset_variants is None:
            missing.append(f"onset={onset_key}")
        if vowel_key and vowel_variants is None:
            missing.append(f"vowel={vowel_key}")
        if coda_key and coda_variants is None:
            missing.append(f"coda={coda_key}")

        if missing:
            status = f"missing: {', '.join(missing)}"
            all_found = False
            # Fall back to raw syllable romanization
            syllable_options.append([syl.romanization])
        else:
            # Cartesian product of component variants
            onset_v = onset_variants or [""]
            vowel_v = vowel_variants or [""]
            coda_v = coda_variants or [""]
            syl_variants = sorted(set(
                o + v + c for o, v, c in product(onset_v, vowel_v, coda_v)
            ))
            syllable_options.append(syl_variants)

        diagnostics.append({
            "syllable": syl.thai_text,
            "romanization": syl.romanization,
            "status": status,
            "onset": onset_key,
            "vowel": vowel_key,
            "coda": coda_key,
        })

    # Cartesian product across syllables
    all_variants: set[str] = set()
    for combo in product(*syllable_options):
        all_variants.add("".join(combo))

    return sorted(all_variants), diagnostics


def main() -> None:
    if not DICT_PATH.exists():
        print(f"ERROR: Dictionary not found: {DICT_PATH}")
        sys.exit(1)
    if not BENCHMARK_PATH.exists():
        print(f"ERROR: Benchmark not found: {BENCHMARK_PATH}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dictionary = load_dictionary(DICT_PATH)
    benchmark = load_benchmark(BENCHMARK_PATH)

    print(f"Dictionary: {DICT_PATH.name}")
    print(f"  Onsets:  {len(dictionary.get('onsets', {}))}")
    print(f"  Vowels:  {len(dictionary.get('vowels', {}))}")
    print(f"  Codas:   {len(dictionary.get('codas', {}))}")
    print(f"Benchmark: {len(benchmark)} unique Thai words, "
          f"{sum(len(v) for v in benchmark.values())} total entries")

    # --- Run validation ---
    total_benchmark_entries = 0
    matched_entries = 0
    total_generated = 0
    total_syllables = 0
    syllables_with_missing = 0
    words_fully_covered = 0
    words_with_fallback = 0
    words_failed = 0

    per_word_results: list[dict] = []
    all_missing_components: list[dict] = []

    for thai_word, expected_latins in sorted(benchmark.items()):
        variants, diagnostics = generate_variants_from_dict(thai_word, dictionary)

        if not variants:
            words_failed += 1
            per_word_results.append({
                "thai_word": thai_word,
                "expected_count": len(expected_latins),
                "generated_count": 0,
                "matched_count": 0,
                "status": "failed",
                "matched_entries": "",
                "missed_entries": "; ".join(sorted(expected_latins)),
            })
            total_benchmark_entries += len(expected_latins)
            continue

        # Check for fallbacks
        has_fallback = any(d["status"] != "ok" for d in diagnostics)
        if has_fallback:
            words_with_fallback += 1
        else:
            words_fully_covered += 1

        # Count syllable-level coverage
        for d in diagnostics:
            total_syllables += 1
            if d["status"] not in ("ok", "tltk_failed"):
                syllables_with_missing += 1
                all_missing_components.append({
                    "word": thai_word,
                    "syllable": d.get("syllable", ""),
                    "romanization": d.get("romanization", ""),
                    "status": d["status"],
                    "onset": d.get("onset", ""),
                    "vowel": d.get("vowel", ""),
                    "coda": d.get("coda", ""),
                })

        # Match against benchmark
        variant_set = set(variants)
        matched = expected_latins & variant_set
        missed = expected_latins - variant_set

        total_benchmark_entries += len(expected_latins)
        matched_entries += len(matched)
        total_generated += len(variants)

        per_word_results.append({
            "thai_word": thai_word,
            "expected_count": len(expected_latins),
            "generated_count": len(variants),
            "matched_count": len(matched),
            "status": "fallback" if has_fallback else "ok",
            "matched_entries": "; ".join(sorted(matched)),
            "missed_entries": "; ".join(sorted(missed)),
        })

    # --- Print results ---
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")

    print(f"\nWord-level:")
    total_words = len(benchmark)
    print(f"  Fully covered (dict): {words_fully_covered}/{total_words} "
          f"({100*words_fully_covered/total_words:.1f}%)")
    print(f"  With fallback:        {words_with_fallback}/{total_words} "
          f"({100*words_with_fallback/total_words:.1f}%)")
    print(f"  Failed (no output):   {words_failed}/{total_words} "
          f"({100*words_failed/total_words:.1f}%)")

    print(f"\nComponent coverage:")
    covered_syllables = total_syllables - syllables_with_missing
    print(f"  Syllables with all components in dict: {covered_syllables}/{total_syllables} "
          f"({100*covered_syllables/total_syllables:.1f}%)")
    print(f"  Syllables with missing components:     {syllables_with_missing}/{total_syllables}")

    print(f"\nBenchmark reproduction:")
    print(f"  Benchmark entries matched: {matched_entries}/{total_benchmark_entries} "
          f"({100*matched_entries/total_benchmark_entries:.1f}%)")
    print(f"  Benchmark entries missed:  {total_benchmark_entries - matched_entries}/"
          f"{total_benchmark_entries}")
    print(f"  Total variants generated:  {total_generated}")

    noise = total_generated - matched_entries
    print(f"\nNoise (generated but not in benchmark):")
    print(f"  {noise} variants ({100*noise/total_generated:.1f}% of generated)")

    # --- Write detailed results ---
    results_path = OUTPUT_DIR / "validation_results.csv"
    with open(results_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "thai_word", "expected_count", "generated_count",
            "matched_count", "status", "matched_entries", "missed_entries",
        ])
        writer.writeheader()
        writer.writerows(per_word_results)
    print(f"\nPer-word results: {results_path.name}")

    # --- Write missing components ---
    if all_missing_components:
        missing_path = OUTPUT_DIR / "missing_components.csv"
        with open(missing_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "word", "syllable", "romanization", "status",
                "onset", "vowel", "coda",
            ])
            writer.writeheader()
            writer.writerows(all_missing_components)
        print(f"Missing components: {missing_path.name}")

    # --- Write missed benchmark entries for analysis ---
    missed_path = OUTPUT_DIR / "missed_benchmark_entries.csv"
    missed_rows = []
    for r in per_word_results:
        if r["missed_entries"]:
            for entry in r["missed_entries"].split("; "):
                missed_rows.append({
                    "thai_word": r["thai_word"],
                    "latin_input": entry,
                    "word_status": r["status"],
                    "generated_count": r["generated_count"],
                })
    with open(missed_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "thai_word", "latin_input", "word_status", "generated_count",
        ])
        writer.writeheader()
        writer.writerows(missed_rows)
    print(f"Missed entries:   {missed_path.name}")


if __name__ == "__main__":
    main()
