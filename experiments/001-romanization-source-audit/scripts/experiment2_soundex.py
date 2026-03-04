"""
Experiment 2: Soundex/Phonetic Algorithm Evaluation

Tests cross-language soundex matching between Thai words and their
romanizations. Evaluates whether phonetic hashing can serve as a
fuzziness mechanism for trie lookup.
"""

import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
DATA_DIR = EXPERIMENT_DIR / "data"


def load_experiment1_results():
    """Load results from experiment 1."""
    path = DATA_DIR / "experiment1_results.csv"
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def run_soundex_experiment():
    """Test cross-language soundex matching."""
    from pythainlp.soundex import soundex

    results = load_experiment1_results()
    engines_to_test = ["tltk_roman", "pythainlp_royin", "informal_ref"]

    print("=" * 100)
    print("SOUNDEX CROSS-LANGUAGE MATCHING (prayut_and_somchaip engine)")
    print("=" * 100)

    match_counts = {eng: 0 for eng in engines_to_test}
    total = 0
    detailed_results = []

    for r in results:
        thai = r["thai"]
        thai_code = soundex(thai, engine="prayut_and_somchaip")
        total += 1

        row = {"thai": thai, "english": r["english"], "thai_soundex": thai_code}

        for eng in engines_to_test:
            latin = r[eng]
            if latin.startswith("ERROR") or not latin.strip():
                row[f"{eng}_soundex"] = "N/A"
                row[f"{eng}_match"] = False
                continue

            latin_code = soundex(latin, engine="prayut_and_somchaip")
            match = thai_code == latin_code
            row[f"{eng}_soundex"] = latin_code
            row[f"{eng}_match"] = match
            if match:
                match_counts[eng] += 1

        detailed_results.append(row)

    # Print results
    print(f"\nTotal words tested: {total}\n")
    print("Match rates (Thai soundex == Latin soundex):")
    for eng in engines_to_test:
        rate = match_counts[eng] / total * 100
        print(f"  {eng:<25} {match_counts[eng]}/{total} ({rate:.1f}%)")

    # Show examples of matches and mismatches
    print("\n--- Sample matches ---")
    for r in detailed_results[:20]:
        thai = r["thai"]
        thai_sx = r["thai_soundex"]
        for eng in engines_to_test:
            sx_key = f"{eng}_soundex"
            match_key = f"{eng}_match"
            if r.get(match_key):
                print(f"  MATCH: {thai} [{thai_sx}] == {eng} [{r[sx_key]}]")

    print("\n--- Sample mismatches ---")
    for r in detailed_results[:20]:
        thai = r["thai"]
        thai_sx = r["thai_soundex"]
        for eng in engines_to_test:
            sx_key = f"{eng}_soundex"
            match_key = f"{eng}_match"
            if not r.get(match_key) and r.get(sx_key) != "N/A":
                print(f"  MISS:  {thai} [{thai_sx}] != {eng} [{r[sx_key]}]")

    # Save detailed results
    output_path = DATA_DIR / "experiment2_soundex.csv"
    fieldnames = ["thai", "english", "thai_soundex"]
    for eng in engines_to_test:
        fieldnames.extend([f"{eng}_soundex", f"{eng}_match"])

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detailed_results)

    print(f"\nDetailed results saved to {output_path}")

    # Test collision rate: pick 20 unrelated word pairs and check if they match
    print("\n--- Collision test (unrelated word pairs) ---")
    collisions = 0
    pairs_tested = 0
    for i in range(min(20, len(results))):
        for j in range(i + 1, min(20, len(results))):
            if results[i]["category"] != results[j]["category"]:
                thai1 = results[i]["thai"]
                thai2 = results[j]["thai"]
                code1 = soundex(thai1, engine="prayut_and_somchaip")
                code2 = soundex(thai2, engine="prayut_and_somchaip")
                pairs_tested += 1
                if code1 == code2:
                    collisions += 1
                    print(f"  COLLISION: {thai1} [{code1}] == {thai2} [{code2}]")

    print(
        f"\nCollision rate: {collisions}/{pairs_tested} ({collisions/max(pairs_tested,1)*100:.1f}%)"
    )


if __name__ == "__main__":
    run_soundex_experiment()
