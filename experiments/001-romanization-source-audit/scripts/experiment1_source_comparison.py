"""
Experiment 1: Programmatic Source Comparison

Runs all available romanization engines on the sample word set and
collects outputs in a comparison table.
"""

import csv
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Paths
SCRIPT_DIR = Path(__file__).parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
DATA_DIR = EXPERIMENT_DIR / "data"
SAMPLE_WORDS = DATA_DIR / "sample_words.csv"


def load_sample_words():
    """Load the sample word set."""
    with open(SAMPLE_WORDS, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def romanize_tltk(word: str) -> str:
    """TLTK th2roman - RTGS-like rule-based."""
    import tltk

    try:
        result = tltk.nlp.th2roman(word)
        # Clean up TLTK output (remove sentence boundary markers)
        result = result.replace("<s/>", "").replace("<tr/>", "").strip().rstrip("-")
        return result
    except Exception as e:
        return f"ERROR: {e}"


def romanize_tltk_ipa(word: str) -> str:
    """TLTK th2ipa - IPA transcription."""
    import tltk

    try:
        result = tltk.nlp.th2ipa(word)
        result = result.replace("<s/>", "").replace("<tr/>", "").strip().rstrip("-")
        return result
    except Exception as e:
        return f"ERROR: {e}"


def romanize_pythainlp_royin(word: str) -> str:
    """PyThaiNLP royin engine - RTGS rule-based."""
    from pythainlp.transliterate import romanize

    try:
        return romanize(word, engine="royin")
    except Exception as e:
        return f"ERROR: {e}"


def romanize_pythainlp_thai2rom(word: str) -> str:
    """PyThaiNLP thai2rom engine - Seq2Seq deep learning."""
    from pythainlp.transliterate import romanize

    try:
        return romanize(word, engine="thai2rom")
    except Exception as e:
        return f"ERROR: {e}"


def romanize_pythainlp_lookup(word: str) -> str:
    """PyThaiNLP lookup engine - dictionary lookup."""
    from pythainlp.transliterate import romanize

    try:
        return romanize(word, engine="lookup")
    except Exception as e:
        return f"ERROR: {e}"


def romanize_iso11940(word: str) -> str:
    """PyThaiNLP ISO 11940 transliteration."""
    from pythainlp.transliterate import transliterate

    try:
        return transliterate(word, engine="iso_11940")
    except Exception as e:
        return f"ERROR: {e}"


ENGINES = {
    "tltk_roman": romanize_tltk,
    "tltk_ipa": romanize_tltk_ipa,
    "pythainlp_royin": romanize_pythainlp_royin,
    "pythainlp_thai2rom": romanize_pythainlp_thai2rom,
    "pythainlp_lookup": romanize_pythainlp_lookup,
    "iso_11940": romanize_iso11940,
}


def run_experiment():
    """Run all engines on all sample words."""
    words = load_sample_words()
    results = []

    print(f"Running {len(ENGINES)} engines on {len(words)} words...\n")

    for i, word_entry in enumerate(words):
        thai = word_entry["thai"]
        row = {
            "thai": thai,
            "category": word_entry["category"],
            "english": word_entry["english_gloss"],
            "informal_ref": word_entry["informal_romanization"],
        }

        for engine_name, engine_func in ENGINES.items():
            row[engine_name] = engine_func(thai)

        results.append(row)

        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(words)} words...")

    print(f"  Done! Processed all {len(words)} words.\n")
    return results


def save_results(results):
    """Save results to CSV."""
    output_path = DATA_DIR / "experiment1_results.csv"
    fieldnames = [
        "thai",
        "category",
        "english",
        "informal_ref",
    ] + list(ENGINES.keys())

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Results saved to {output_path}")
    return output_path


def print_comparison_table(results):
    """Print a readable comparison table."""
    # Print header
    engines = list(ENGINES.keys())

    print("=" * 120)
    print("ROMANIZATION SOURCE COMPARISON")
    print("=" * 120)

    for category in [
        "common",
        "food",
        "places",
        "verbs",
        "slang",
        "compounds",
        "loanwords",
    ]:
        cat_results = [r for r in results if r["category"] == category]
        if not cat_results:
            continue

        print(f"\n--- {category.upper()} ---\n")
        print(
            f"{'Thai':<15} {'English':<15} {'Informal':<15} {'tltk':<15} {'royin':<15} {'thai2rom':<18} {'lookup':<15}"
        )
        print("-" * 120)

        for r in cat_results:
            print(
                f"{r['thai']:<15} {r['english']:<15} {r['informal_ref']:<15} "
                f"{r['tltk_roman']:<15} {r['pythainlp_royin']:<15} "
                f"{r['pythainlp_thai2rom']:<18} {r['pythainlp_lookup']:<15}"
            )

    # Summary statistics
    print("\n" + "=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)

    for engine_name in engines:
        errors = sum(1 for r in results if r[engine_name].startswith("ERROR"))
        empty = sum(1 for r in results if r[engine_name].strip() == "")
        print(
            f"{engine_name:<25} errors={errors}, empty={empty}, successful={len(results) - errors - empty}"
        )


if __name__ == "__main__":
    results = run_experiment()
    save_results(results)
    print_comparison_table(results)
