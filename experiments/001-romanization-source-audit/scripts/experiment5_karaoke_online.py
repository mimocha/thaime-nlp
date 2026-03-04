#!/usr/bin/env python3
"""
Experiment 5: Karaoke & Online Source Evaluation

Tests thpronun (TLWG), analyzes thai2karaoke (GitHub), and evaluates
web-based romanization sources (thai-language.com, thai2english.com).

This extends the original audit (experiments 1-4) with sources that
were catalogued but not tested.
"""

import csv
import json
import subprocess
import os
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
SAMPLE_WORDS_PATH = os.path.join(DATA_DIR, "sample_words.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "experiment5_karaoke_online.csv")
THPRONUN_STATS_PATH = os.path.join(DATA_DIR, "experiment5_thpronun_stats.json")


def load_sample_words():
    """Load the 80-word sample set."""
    words = []
    with open(SAMPLE_WORDS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append(row)
    return words


def run_thpronun(thai_word: str) -> dict:
    """
    Run thpronun on a single Thai word and parse the output.

    Returns a dict with keys:
      - thai_pron: list of Thai pronunciation readings
      - roman: list of romanization readings
      - phonetic: list of phonetic code readings
      - error: error message if any
    """
    result = {
        "thai_pron": [],
        "roman": [],
        "phonetic": [],
        "error": None,
    }

    try:
        proc = subprocess.run(
            ["thpronun", "-r", "-t", "-p", thai_word],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if not output:
            result["error"] = stderr or "no output"
            return result

        # thpronun outputs 3 blocks separated by blank lines:
        # 1. Thai pronunciation readings
        # 2. Romanization readings
        # 3. Phonetic code readings
        # Each block is preceded by the word + ":"
        lines = output.split("\n")

        # Skip the first line (word:) and warnings
        content_lines = []
        for line in lines:
            if line.startswith("Failed to load") or line.startswith("Warning:"):
                continue
            content_lines.append(line)

        # Find the word header line
        blocks = []
        current_block = []
        header_seen = False

        for line in content_lines:
            if line.strip().endswith(":") and not header_seen:
                header_seen = True
                continue
            if line.strip() == "":
                if current_block:
                    blocks.append(current_block)
                    current_block = []
            else:
                current_block.append(line.strip())

        if current_block:
            blocks.append(current_block)

        if len(blocks) >= 1:
            result["thai_pron"] = blocks[0]
        if len(blocks) >= 2:
            result["roman"] = blocks[1]
        if len(blocks) >= 3:
            result["phonetic"] = blocks[2]

    except FileNotFoundError:
        result["error"] = "thpronun not installed"
    except subprocess.TimeoutExpired:
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = str(e)

    return result


def run_thpronun_json(thai_word: str) -> dict:
    """
    Run thpronun with JSON output for structured romanization.

    Returns dict with:
      - syllables: list of lists of syllable romanizations (one per reading)
      - unique_romans: set of unique full romanization strings
      - error: error message if any
    """
    result = {"syllables": [], "unique_romans": set(), "error": None}

    try:
        proc = subprocess.run(
            ["thpronun", "-r", "-j", thai_word],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = proc.stdout.strip()

        # Extract JSON part (after the "word:" header)
        lines = output.split("\n")
        json_line = None
        for line in lines:
            line = line.strip()
            if line.startswith("["):
                json_line = line
                break

        if json_line:
            readings = json.loads(json_line)
            result["syllables"] = readings
            for reading in readings:
                result["unique_romans"].add("".join(reading))

    except FileNotFoundError:
        result["error"] = "thpronun not installed"
    except Exception as e:
        result["error"] = str(e)

    return result


def evaluate_thpronun(words):
    """Run thpronun on all sample words and collect results."""
    results = []

    for word_info in words:
        thai = word_info["thai"]
        category = word_info["category"]
        english = word_info["english_gloss"]
        informal = word_info["informal_romanization"]

        # Get plain-text output
        plain = run_thpronun(thai)

        # Get JSON output for structured data
        json_out = run_thpronun_json(thai)

        # Pick the "best" (shortest/cleanest) romanization
        best_roman = ""
        if json_out["unique_romans"]:
            # Pick the shortest unique romanization as representative
            sorted_romans = sorted(json_out["unique_romans"], key=len)
            best_roman = sorted_romans[0]
        elif plain["roman"]:
            best_roman = plain["roman"][-1]  # Last is often the simplest

        results.append(
            {
                "thai": thai,
                "category": category,
                "english": english,
                "informal_ref": informal,
                "thpronun_best": best_roman,
                "thpronun_all_romans": "|".join(sorted(json_out["unique_romans"])) if json_out["unique_romans"] else "",
                "thpronun_num_readings": len(json_out["syllables"]),
                "thpronun_syllables": json.dumps(json_out["syllables"][:3], ensure_ascii=False) if json_out["syllables"] else "",
                "thpronun_error": plain["error"] or "",
            }
        )

    return results


def analyze_thai2karaoke():
    """
    Analyze the thai2karaoke project structure and approach.
    Returns a summary dict (does not require running the tool).
    """
    analysis = {
        "name": "thai2karaoke (comdevx)",
        "type": "Neural network (brain.js) syllable classifier",
        "language": "JavaScript (Node.js)",
        "license": "Open source (attribution requested)",
        "approach": (
            "Uses a neural network trained on Thai syllable patterns to classify "
            "syllables into vowel-sound groups (e.g., 'a', 'i', 'ue', 'o', 'ai', etc.). "
            "Then assembles romanization by looking up initial/final consonant mappings "
            "from a character table and combining with the classified vowel group."
        ),
        "consonant_system": {
            "initial_mapping": "RTGS-like (ก→k, ข→kh, ค→kh, จ→ch, etc.)",
            "final_mapping": "Simplified (จ→t, ซ→t, บ→p, ด→t, etc.)",
            "note": "Uses 'first' for initial position and 'spell' for final position per consonant",
        },
        "vowel_groups": [
            "a, a1-a8 (sara a variants)",
            "i, i1-i4 (sara i variants)",
            "ue, ue1-ue4 (sara ue variants)",
            "u, u1-u4 (sara u variants)",
            "e, e1-e4 (sara e variants)",
            "ae, ae1-ae2 (sara ae variants)",
            "o, o1-o5 (sara o variants)",
            "oe, oe1-oe3 (sara oe variants)",
            "ia, ia1-ia2 (sara ia variants)",
            "uea, uea1-uea4 (sara uea variants)",
            "ua, ua1-ua4 (sara ua variants)",
            "ai, ai1 (sara ai variants)",
            "ao, ao1-ao2 (sara ao variants)",
            "ui, ui1 (sara ui variants)",
            "oei (sara oei)",
            "am (sara am)",
            "an (double ร)",
        ],
        "training_data_size": "~600 syllable patterns",
        "strengths": [
            "Syllable-aligned output (each Thai syllable → Latin chunk)",
            "Uses neural network to handle ambiguous vowel patterns",
            "RTGS-based consonant mapping is correct",
        ],
        "weaknesses": [
            "Requires pre-segmented Thai syllables (word segmentation not included)",
            "Small training set (~600 patterns)",
            "Node.js only (not directly usable in Python pipeline)",
            "No maintenance for 6+ years (last updated 2019)",
            "No tone handling",
            "Neural network adds complexity vs. simple rule-based approach",
        ],
        "relevance_to_thaime": (
            "Low. The consonant and vowel mappings are a subset of what TLTK already "
            "provides with better quality. The syllable-level approach is interesting "
            "conceptually but the tool itself is not practically usable. The character "
            "mapping tables (find_word.js) could be referenced for validation."
        ),
    }
    return analysis


def analyze_web_sources():
    """
    Document the analysis of web-based romanization sources.
    Returns list of source analysis dicts.
    """
    sources = []

    # thai-language.com
    sources.append({
        "name": "thai-language.com",
        "url": "http://www.thai-language.com/",
        "size": "30,000+ dictionary entries",
        "romanization_system": (
            "Custom phonemic system with tone markers using capital letters: "
            "M=mid, L=low, H=high, F=falling, R=rising. "
            "Example: สวัสดี → 'saL watL deeM'. "
            "Also shows RTGS (Royal Thai General System) in a separate field."
        ),
        "example_romanizations": {
            "ชา": "chaaM (with tone marker)",
            "น้ำชา": "namH chaaM",
            "กรุงเทพ": "grungM thaehpF (per RTGS section: krung thep)",
        },
        "api_access": "No public API. Has a 'bulk lookup' feature for registered users.",
        "scraping_feasibility": (
            "Pages are server-rendered HTML with consistent structure. "
            "Dictionary entries have numeric IDs (e.g., /id/131163). "
            "Could be scraped, but ToS likely prohibits systematic extraction."
        ),
        "license": "Proprietary. Copyright notice present. No open data license.",
        "strengths": [
            "Very high quality, human-curated entries",
            "Multiple romanization systems per entry (custom phonemic + RTGS)",
            "Tone information preserved",
            "Rich example sentences with full romanization",
            "Large vocabulary including colloquial Thai",
        ],
        "weaknesses": [
            "No API for programmatic access",
            "Proprietary — cannot legally extract data at scale",
            "Custom romanization system (not RTGS) requires post-processing",
            "Tone markers use capital letters which need stripping for THAIME use",
        ],
        "relevance_to_thaime": (
            "High quality but not legally or practically extractable at scale. "
            "Could serve as a manual validation/reference source for spot-checking "
            "romanization quality. The tone-marked system is not directly useful for "
            "THAIME (users don't type tones), but the base romanizations are good."
        ),
    })

    # thai2english.com
    sources.append({
        "name": "thai2english.com",
        "url": "https://www.thai2english.com/",
        "size": "100,000+ entries (claimed)",
        "romanization_system": (
            "Custom system with diacritic tone markers: "
            "â=falling, à=low, ǎ=rising, etc. "
            "Example: กรุงเทพ → 'grung tâyp'. "
            "Notable differences from RTGS: uses 'g' for ก (not 'k'), "
            "'bp' for ป (not 'p'), 'dt' for ต (not 't')."
        ),
        "example_romanizations": {
            "กรุงเทพ": "grung tâyp",
            "เป็น": "bpen",
            "เมืองหลวง": "meuang lŭang",
            "ประเทศไทย": "bprà-tâyt tai",
        },
        "api_access": (
            "No documented public API. The transliteration feature works "
            "client-side via JavaScript. Could potentially reverse-engineer "
            "the API endpoint but this is against ToS."
        ),
        "scraping_feasibility": (
            "The site uses client-side rendering for transliteration. "
            "Dictionary pages might be scrapable but ToS likely prohibits it."
        ),
        "license": "Proprietary. Copyright © 2024 thai2english.com.",
        "strengths": [
            "High-quality romanization with tone markers",
            "Word segmentation built in",
            "Includes component word breakdowns",
            "Example sentences with full romanization",
            "Designed specifically for learners (readable output)",
        ],
        "weaknesses": [
            "Proprietary — no data extraction allowed",
            "Custom romanization system different from RTGS",
            "Uses 'g' instead of 'k', 'bp' instead of 'p' — closer to Thai phonology but not intuitive for informal romanization",
            "Diacritic tone markers not useful for THAIME",
        ],
        "relevance_to_thaime": (
            "Medium. The romanization system is phonologically accurate but uses "
            "a non-standard convention (g/bp/dt) that doesn't match either RTGS or "
            "informal romanization patterns. Not extractable at scale. "
            "Could be used as a validation reference."
        ),
    })

    # Wiktionary
    sources.append({
        "name": "Wiktionary (Thai entries)",
        "url": "https://en.wiktionary.org/wiki/Category:Thai_terms_with_IPA_pronunciation",
        "size": "16,000+ Thai entries with IPA pronunciation",
        "romanization_system": (
            "Multiple systems per entry: IPA, RTGS, and Paiboon+. "
            "Structured data extractable via wiktextract tool. "
            "Example: สวัสดี has RTGS 'sawatdi', IPA '/sa.wàt.dīː/', Paiboon 'sà-wàt-dee'."
        ),
        "example_romanizations": {
            "note": "Based on Wiktionary entry format, not live-tested",
            "สวัสดี": "RTGS: sawatdi, IPA: /sa.wàt.dīː/, Paiboon: sà-wàt-dee",
        },
        "api_access": (
            "Structured data available via wiktextract (Python tool). "
            "Wiktionary also has a MediaWiki API for raw wikitext. "
            "Pre-extracted data dumps available from kaikki.org."
        ),
        "scraping_feasibility": "Fully legal — CC-BY-SA 3.0 license.",
        "license": "CC-BY-SA 3.0 (requires attribution, share-alike)",
        "strengths": [
            "Multiple romanization systems (RTGS, IPA, Paiboon)",
            "Open license (CC-BY-SA 3.0)",
            "Structured data extractable via wiktextract",
            "Community-curated with quality standards",
            "Paiboon system is closest to learner-friendly romanization",
        ],
        "weaknesses": [
            "Only 16K+ entries (smaller than thai2rom-dataset)",
            "Coverage focuses on common vocabulary, may miss slang",
            "wiktextract extraction requires processing effort",
            "CC-BY-SA 3.0 share-alike may have implications for THAIME (MPL 2.0)",
        ],
        "relevance_to_thaime": (
            "High. The multi-system romanization data is uniquely valuable — "
            "no other source provides RTGS + IPA + Paiboon in structured form. "
            "The Paiboon romanizations may be the closest available approximation "
            "to informal romanization. The CC-BY-SA license needs legal review "
            "for compatibility with THAIME's MPL 2.0 license. "
            "Recommended as a follow-up investigation."
        ),
    })

    return sources


def compute_thpronun_stats(results):
    """Compute summary statistics for thpronun results."""
    total = len(results)
    errors = sum(1 for r in results if r["thpronun_error"])
    has_output = sum(1 for r in results if r["thpronun_best"])
    multi_reading = sum(1 for r in results if r["thpronun_num_readings"] > 1)

    # Compare best thpronun romanization with informal reference
    exact_matches = 0
    close_matches = 0  # Same after normalizing common variations
    for r in results:
        if not r["thpronun_best"]:
            continue
        best = r["thpronun_best"].lower().replace("-", "")
        informal = r["informal_ref"].lower().replace(" ", "")
        if best == informal:
            exact_matches += 1
        # Check for "close" match: strip common differences
        elif normalize_roman(best) == normalize_roman(informal):
            close_matches += 1

    # Count readings distribution
    reading_counts = {}
    for r in results:
        n = r["thpronun_num_readings"]
        reading_counts[n] = reading_counts.get(n, 0) + 1

    stats = {
        "total_words": total,
        "errors": errors,
        "has_output": has_output,
        "multi_reading_words": multi_reading,
        "exact_match_with_informal": exact_matches,
        "close_match_with_informal": close_matches,
        "match_rate_exact": f"{exact_matches / total * 100:.1f}%",
        "match_rate_close": f"{(exact_matches + close_matches) / total * 100:.1f}%",
        "readings_distribution": dict(sorted(reading_counts.items())),
        "avg_readings_per_word": sum(r["thpronun_num_readings"] for r in results) / total,
    }
    return stats


def normalize_roman(s):
    """Normalize romanization for fuzzy comparison."""
    s = s.lower().replace("-", "").replace(" ", "")
    # Common variations
    s = s.replace("ph", "p").replace("th", "t").replace("kh", "k")
    s = s.replace("ee", "i").replace("oo", "u").replace("aa", "a")
    return s


def main():
    print("=" * 60)
    print("Experiment 5: Karaoke & Online Source Evaluation")
    print("=" * 60)

    # Load sample words
    words = load_sample_words()
    print(f"\nLoaded {len(words)} sample words")

    # ---- Part 1: thpronun evaluation ----
    print("\n--- Part 1: thpronun (TLWG) Evaluation ---")
    thpronun_results = evaluate_thpronun(words)

    # Save CSV results
    fieldnames = [
        "thai", "category", "english", "informal_ref",
        "thpronun_best", "thpronun_all_romans", "thpronun_num_readings",
        "thpronun_syllables", "thpronun_error",
    ]
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(thpronun_results)
    print(f"Results saved to {OUTPUT_PATH}")

    # Compute and save stats
    stats = compute_thpronun_stats(thpronun_results)
    print(f"\nthpronun statistics:")
    print(f"  Total words: {stats['total_words']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Words with output: {stats['has_output']}")
    print(f"  Words with multiple readings: {stats['multi_reading_words']}")
    print(f"  Exact match with informal: {stats['exact_match_with_informal']} ({stats['match_rate_exact']})")
    print(f"  Close match with informal: {stats['close_match_with_informal']}")
    print(f"  Combined match rate: {stats['match_rate_close']}")
    print(f"  Avg readings per word: {stats['avg_readings_per_word']:.1f}")
    print(f"  Readings distribution: {stats['readings_distribution']}")

    # Print comparison table for key words
    print("\n  Key word comparisons:")
    print(f"  {'Thai':<15} {'Informal':<15} {'thpronun best':<20} {'# readings'}")
    print(f"  {'-'*15} {'-'*15} {'-'*20} {'-'*10}")
    key_words = ["สวัสดี", "ขอบคุณ", "กรุงเทพ", "เชียงใหม่", "ต้มยำกุ้ง",
                 "ส้มตำ", "อยุธยา", "หาดใหญ่", "ครับ", "อร่อย",
                 "แท็กซี่", "อินเทอร์เน็ต", "เฟซบุ๊ก", "ฟุตบอล"]
    for r in thpronun_results:
        if r["thai"] in key_words:
            print(f"  {r['thai']:<15} {r['informal_ref']:<15} {r['thpronun_best']:<20} {r['thpronun_num_readings']}")

    # ---- Part 2: thai2karaoke analysis ----
    print("\n--- Part 2: thai2karaoke Analysis ---")
    t2k_analysis = analyze_thai2karaoke()
    print(f"  Tool: {t2k_analysis['name']}")
    print(f"  Type: {t2k_analysis['type']}")
    print(f"  Language: {t2k_analysis['language']}")
    print(f"  Training data: {t2k_analysis['training_data_size']}")
    print(f"  Relevance: {t2k_analysis['relevance_to_thaime']}")

    # ---- Part 3: Web source analysis ----
    print("\n--- Part 3: Web Source Analysis ---")
    web_sources = analyze_web_sources()
    for src in web_sources:
        print(f"\n  {src['name']} ({src['url']})")
        print(f"    Size: {src['size']}")
        print(f"    License: {src['license']}")
        print(f"    Romanization: {src['romanization_system'][:80]}...")
        print(f"    Relevance: {src['relevance_to_thaime'][:80]}...")

    # ---- Save full analysis as JSON ----
    full_analysis = {
        "thpronun_stats": stats,
        "thai2karaoke_analysis": t2k_analysis,
        "web_sources": web_sources,
    }
    with open(THPRONUN_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(full_analysis, f, indent=2, ensure_ascii=False)
    print(f"\nFull analysis saved to {THPRONUN_STATS_PATH}")

    print("\n" + "=" * 60)
    print("Experiment 5 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
