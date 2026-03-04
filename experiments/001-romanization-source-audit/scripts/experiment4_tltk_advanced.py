"""
Experiment 4: TLTK Advanced Features

Tests TLTK's th2ipa_all() for pronunciation ambiguity and
spell_variants() for alternative spellings. Evaluates whether
these features can help generate romanization variants.
"""

import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
DATA_DIR = EXPERIMENT_DIR / "data"


def load_sample_words():
    path = DATA_DIR / "sample_words.csv"
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def test_ipa_all():
    """Test th2ipa_all to see how many ambiguous readings exist."""
    import tltk

    words = load_sample_words()

    print("=" * 100)
    print("TLTK th2ipa_all() - Pronunciation Ambiguity")
    print("=" * 100)

    ambiguous_count = 0
    total = 0

    for w in words:
        thai = w["thai"]
        total += 1
        try:
            all_readings = tltk.nlp.th2ipa_all(thai)
            n = len(all_readings)
            if n > 1:
                ambiguous_count += 1
                print(f"\n  {thai} ({w['english']}) - {n} readings:")
                for parse, ipa in all_readings[:5]:  # Show max 5
                    print(f"    {parse} -> {ipa}")
                if n > 5:
                    print(f"    ... and {n - 5} more")
        except Exception as e:
            print(f"  {thai}: ERROR - {e}")

    print(f"\n\nSummary: {ambiguous_count}/{total} words have multiple readings ({ambiguous_count/total*100:.1f}%)")


def test_spell_variants():
    """Test spell_variants to find alternative Thai spellings."""
    import tltk

    words = load_sample_words()

    print("\n" + "=" * 100)
    print("TLTK spell_variants() - Alternative Thai Spellings")
    print("=" * 100)

    has_variants_count = 0
    total = 0

    for w in words:
        thai = w["thai"]
        total += 1
        try:
            variants = tltk.nlp.spell_variants(thai)
            if variants and len(variants) > 1:
                has_variants_count += 1
                print(f"\n  {thai} ({w['english']}):")
                for v in variants[:8]:
                    print(f"    {v}")
                if len(variants) > 8:
                    print(f"    ... and {len(variants) - 8} more")
            elif variants and len(variants) == 1:
                pass  # Only the word itself
        except Exception as e:
            print(f"  {thai}: ERROR - {e}")

    print(f"\n\nSummary: {has_variants_count}/{total} words have spelling variants ({has_variants_count/total*100:.1f}%)")


def test_g2p_internals():
    """Examine TLTK g2p internals for selected words."""
    import tltk

    print("\n" + "=" * 100)
    print("TLTK g2p() - Internal Phonemic Representation")
    print("=" * 100)

    # Test a focused set of interesting words
    test_words = [
        ("สวัสดี", "hello"),
        ("กรุงเทพ", "Bangkok"),
        ("ประเทศไทย", "Thailand"),
        ("โรงเรียน", "school"),
        ("คอมพิวเตอร์", "computer"),
        ("แท็กซี่", "taxi"),
        ("ข้าว", "rice"),
        ("น้ำ", "water"),
        ("เหนื่อย", "tired"),
        ("อร่อย", "delicious"),
    ]

    for thai, eng in test_words:
        try:
            g2p_out = tltk.nlp.g2p(thai)
            roman = tltk.nlp.th2roman(thai).replace("<s/>", "").strip().rstrip("-")
            ipa = tltk.nlp.th2ipa(thai).replace("<s/>", "").strip().rstrip("-")
            print(f"\n  {thai} ({eng}):")
            print(f"    g2p:   {g2p_out}")
            print(f"    roman: {roman}")
            print(f"    ipa:   {ipa}")
        except Exception as e:
            print(f"  {thai}: ERROR - {e}")


if __name__ == "__main__":
    test_ipa_all()
    test_spell_variants()
    test_g2p_internals()
