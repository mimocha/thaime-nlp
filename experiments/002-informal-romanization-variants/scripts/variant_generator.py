"""Informal Thai Romanization Variant Generator.

Takes TLTK's formal RTGS-like romanization output and generates plausible
informal romanization variants using rule-based transformations.

The generator is:
- Deterministic: same input + config produces the same output
- Configurable: each transformation rule can be toggled independently
- Syllable-aware: uses TLTK's IPA and g2p output to determine vowel length

Design:
    1. Parse TLTK's g2p output to get per-syllable phonetic info
    2. Align TLTK's th2roman output with syllable boundaries
    3. Apply syllable-level transformations based on phonetic properties
    4. Combine syllable variants via Cartesian product
    5. Deduplicate and return sorted list
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import product

import tltk


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class VariantConfig:
    """Configuration for which transformation rules are active."""

    vowel_lengthening: bool = True
    final_consonant_softening: bool = True
    cluster_simplification: bool = True
    r_dropping: bool = True
    initial_voicing: bool = True
    max_variants_per_word: int = 50


DEFAULT_CONFIG = VariantConfig()


# ---------------------------------------------------------------------------
# Phonetic analysis helpers
# ---------------------------------------------------------------------------


@dataclass
class SyllableInfo:
    """Phonetic information about a single syllable."""

    thai_text: str
    romanization: str
    ipa: str
    g2p_group: str
    has_long_vowel: bool = False
    is_open_syllable: bool = False
    final_consonant: str = ""
    initial_cluster: str = ""
    vowel_nucleus: str = ""


def _clean_tltk_output(s: str) -> str:
    """Remove TLTK markup tags from output."""
    return re.sub(r"<[^>]+>", "", s).strip()


def _parse_g2p_groups(g2p_raw: str) -> list[str]:
    """Parse raw g2p output into per-syllable group strings.

    g2p format: สวัส~ดี<tr/>sa1'wat1~dii0|<s/>
    Returns: ["sa1'wat1", "dii0"]
    """
    match = re.search(r"<tr/>([^<]+)", g2p_raw)
    if not match:
        return []
    rom_part = match.group(1).split("|")[0]
    return [g for g in rom_part.split("~") if g]


def _g2p_group_has_long_vowel(group: str) -> bool:
    """Check if a g2p group contains a long vowel."""
    cleaned = re.sub(r"\d", "", group).replace("'", "")
    long_patterns = [
        "aa", "ee", "ii", "oo", "uu",
        "OO", "UU", "xx", "@@",
        "iia", "uua", "UUa",
    ]
    return any(p in cleaned for p in long_patterns)


def _g2p_group_to_approx_roman(group: str) -> str:
    """Convert a g2p group to approximate RTGS romanization length."""
    cleaned = re.sub(r"\d", "", group).replace("'", "")
    replacements = [
        ("iiaw", "iao"), ("iia", "ia"), ("uua", "ua"), ("UUa", "uea"),
        ("aa", "a"), ("ee", "e"), ("ii", "i"), ("oo", "o"), ("uu", "u"),
        ("OO", "o"), ("UU", "ue"), ("xx", "ae"), ("@@", "oe"),
        ("aj", "ai"), ("aw", "ao"),
        ("N", "ng"), ("?", ""),
        ("c", "ch"), ("j", "y"),
    ]
    result = cleaned
    for g2p_v, rtgs_v in replacements:
        result = result.replace(g2p_v, rtgs_v)
    return result


def _split_romanization_by_g2p(
    romanization: str,
    g2p_groups: list[str],
) -> list[str]:
    """Split the whole-word romanization into per-syllable pieces."""
    if len(g2p_groups) <= 1:
        return [romanization]

    result = []
    remaining = romanization

    for i, group in enumerate(g2p_groups):
        if i == len(g2p_groups) - 1:
            result.append(remaining)
            break

        approx = _g2p_group_to_approx_roman(group)
        approx_len = len(approx)

        if 0 < approx_len <= len(remaining):
            best_len = approx_len
            for delta in [0, 1, -1, 2, -2]:
                test_len = approx_len + delta
                if 0 < test_len <= len(remaining):
                    if test_len < len(remaining):
                        next_char = remaining[test_len]
                        if next_char not in "aeiou" and delta == 0:
                            best_len = test_len
                            break
            result.append(remaining[:best_len])
            remaining = remaining[best_len:]
        else:
            split_len = max(1, approx_len if approx_len > 0 else len(remaining) // 2)
            split_len = min(split_len, len(remaining))
            result.append(remaining[:split_len])
            remaining = remaining[split_len:]

    while len(result) < len(g2p_groups):
        result.append("")

    return result


def _detect_final_consonant(roman_syllable: str) -> str:
    """Detect the final consonant of a romanized syllable."""
    if not roman_syllable:
        return ""
    s = roman_syllable.lower()
    if s.endswith("ng"):
        return "ng"
    vowels = set("aeiou")
    if s[-1] not in vowels:
        return s[-1]
    return ""


def _detect_initial_cluster(roman_syllable: str) -> str:
    """Detect the initial consonant cluster of a romanized syllable."""
    if not roman_syllable:
        return ""
    s = roman_syllable.lower()
    clusters = [
        "khr", "thr", "phr",
        "kh", "th", "ph", "ch",
        "kr", "tr", "pr", "kl", "pl", "bl", "fr", "fl",
        "ng",
    ]
    for cluster in clusters:
        if s.startswith(cluster):
            return cluster
    vowels = set("aeiou")
    if s and s[0] not in vowels:
        return s[0]
    return ""


def _detect_vowel_nucleus(
    roman_syllable: str,
    initial_cluster: str,
    final_consonant: str,
) -> str:
    """Extract the vowel nucleus from a romanized syllable."""
    if not roman_syllable:
        return ""
    s = roman_syllable.lower()
    if initial_cluster and s.startswith(initial_cluster):
        s = s[len(initial_cluster):]
    if final_consonant and s.endswith(final_consonant):
        s = s[: -len(final_consonant)]
    return s


def analyze_word(thai_word: str) -> list[SyllableInfo]:
    """Analyze a Thai word using TLTK to get syllable-level phonetic info."""
    roman_raw = tltk.nlp.th2roman(thai_word)
    ipa_raw = tltk.nlp.th2ipa(thai_word)
    g2p_raw = tltk.nlp.g2p(thai_word)
    syl_raw = tltk.nlp.syl_segment(thai_word)

    roman = _clean_tltk_output(roman_raw)
    ipa = _clean_tltk_output(ipa_raw)

    thai_syllables = [s for s in _clean_tltk_output(syl_raw).split("~") if s]
    ipa_syllables = [s.strip() for s in ipa.split(".") if s.strip()]
    g2p_groups = _parse_g2p_groups(g2p_raw)
    syl_romans = _split_romanization_by_g2p(roman, g2p_groups)

    syllable_infos = []
    for i in range(len(thai_syllables)):
        syl_thai = thai_syllables[i]
        syl_roman = syl_romans[i] if i < len(syl_romans) else ""
        syl_ipa = ipa_syllables[i] if i < len(ipa_syllables) else ""
        g2p_group = g2p_groups[i] if i < len(g2p_groups) else ""

        has_long = ("ː" in syl_ipa) or _g2p_group_has_long_vowel(g2p_group)
        final_cons = _detect_final_consonant(syl_roman)
        initial_cluster = _detect_initial_cluster(syl_roman)
        vowel = _detect_vowel_nucleus(syl_roman, initial_cluster, final_cons)
        is_open = (final_cons == "")

        syllable_infos.append(SyllableInfo(
            thai_text=syl_thai,
            romanization=syl_roman,
            ipa=syl_ipa,
            g2p_group=g2p_group,
            has_long_vowel=has_long,
            is_open_syllable=is_open,
            final_consonant=final_cons,
            initial_cluster=initial_cluster,
            vowel_nucleus=vowel,
        ))

    return syllable_infos


# ---------------------------------------------------------------------------
# Transformation rules (component-level)
# ---------------------------------------------------------------------------


def _get_initial_variants(
    syl: SyllableInfo,
    config: VariantConfig,
) -> list[str]:
    """Get all initial-cluster variants for a syllable.

    Returns list of possible initial clusters including the original.
    """
    cluster = syl.initial_cluster
    if not cluster:
        return [""]

    variants = {cluster}

    if config.cluster_simplification:
        # Two-char aspirated cluster simplification
        simplification = {
            "kh": ["k"], "th": ["t"], "ph": ["p"], "ch": ["j", "c"],
        }
        if cluster in simplification:
            variants.update(simplification[cluster])

        # Three-char cluster simplification (drop aspiration, keep r/l)
        three_char = {
            "khr": ["kr"], "thr": ["tr"], "phr": ["pr"],
        }
        if cluster in three_char:
            variants.update(three_char[cluster])

    if config.r_dropping:
        r_drop = {
            "kr": ["k"], "khr": ["kh", "k"],
            "pr": ["p"], "phr": ["ph", "p"],
            "tr": ["t"], "thr": ["th", "t"],
            "fr": ["f"],
        }
        if cluster in r_drop:
            variants.update(r_drop[cluster])

    if config.initial_voicing:
        voicing = {"k": ["g"]}
        if cluster in voicing:
            variants.update(voicing[cluster])

    return sorted(variants)


def _get_vowel_variants(
    syl: SyllableInfo,
    config: VariantConfig,
) -> list[str]:
    """Get all vowel-nucleus variants for a syllable.

    Returns list of possible vowel nuclei including the original.
    """
    vowel = syl.vowel_nucleus
    if not vowel:
        return [""]

    variants = {vowel}

    if config.vowel_lengthening and syl.has_long_vowel:
        # (always_variants, open_syllable_only_variants)
        lengthening: dict[str, tuple[list[str], list[str]]] = {
            "i":   (["ee", "ii"], []),
            "u":   (["oo", "uu"], []),
            "a":   (["aa"],       []),
            "e":   (["ee"],       ["eh"]),
            "o":   (["oo"],       ["oh"]),
            "ue":  (["uee"],      []),
            "ae":  (["aae"],      []),
            "ia":  (["iia"],      []),
            "ua":  (["uaa"],      []),
            "uea": (["ueaa"],     []),
            "ao":  (["aao"],      []),
            "ai":  (["aai"],      []),
            "io":  (["iow", "ew"], []),
        }
        if vowel in lengthening:
            always_v, open_v = lengthening[vowel]
            variants.update(always_v)
            if syl.is_open_syllable:
                variants.update(open_v)

    return sorted(variants)


def _get_final_variants(
    syl: SyllableInfo,
    config: VariantConfig,
) -> list[str]:
    """Get all final-consonant variants for a syllable.

    Returns list of possible final consonants including the original.
    """
    fc = syl.final_consonant
    if not fc:
        return [""]

    variants = {fc}

    if config.final_consonant_softening:
        softening = {"t": "d", "p": "b", "k": "g"}
        if fc in softening:
            variants.add(softening[fc])

    return sorted(variants)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_syllable_variants(
    syl: SyllableInfo,
    config: VariantConfig = DEFAULT_CONFIG,
) -> list[str]:
    """Generate all informal variants for a single syllable.

    Uses component-level Cartesian product: each combination of
    (initial variant × vowel variant × final variant) produces one syllable
    variant. This enables cross-rule combinations like ph→p + u→oo + t→d
    producing "pood" in a single step.
    """
    initials = _get_initial_variants(syl, config)
    vowels = _get_vowel_variants(syl, config)
    finals = _get_final_variants(syl, config)

    all_variants: set[str] = set()
    for init, vow, fin in product(initials, vowels, finals):
        all_variants.add(init + vow + fin)

    # Remove the base form
    all_variants.discard(syl.romanization)

    return sorted(all_variants)


def generate_word_variants(
    thai_word: str,
    config: VariantConfig = DEFAULT_CONFIG,
) -> list[str]:
    """Generate informal romanization variants for a Thai word.

    Returns a sorted, deduplicated list including the base TLTK romanization.
    """
    base_roman = _clean_tltk_output(tltk.nlp.th2roman(thai_word))
    if not base_roman:
        return []

    syllables = analyze_word(thai_word)
    if not syllables:
        return [base_roman]

    syllable_options: list[list[str]] = []
    for syl in syllables:
        options = [syl.romanization]
        options.extend(generate_syllable_variants(syl, config))
        syllable_options.append(options)

    all_variants: set[str] = set()
    for combo in product(*syllable_options):
        all_variants.add("".join(combo))
    all_variants.add(base_roman)

    result = sorted(all_variants)
    if len(result) > config.max_variants_per_word:
        result = [base_roman] + [
            v for v in result if v != base_roman
        ][: config.max_variants_per_word - 1]
        result.sort()

    return result


def generate_variants_for_wordlist(
    thai_words: list[str],
    config: VariantConfig = DEFAULT_CONFIG,
) -> dict[str, list[str]]:
    """Generate variants for a list of Thai words."""
    return {word: generate_word_variants(word, config) for word in thai_words}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo_words = [
        "สวัสดี", "ครับ", "หมู", "ดี", "กรุงเทพ", "ไทย", "กิน",
        "ข้าว", "ผัดไท", "พูด", "ถูก", "โรงเรียน", "หล่อ", "เท่",
    ]
    for word in demo_words:
        variants = generate_word_variants(word)
        print(f"{word}: ({len(variants)} variants) {variants}")
