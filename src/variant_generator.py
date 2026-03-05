"""Informal Thai Romanization Variant Generator.

Takes TLTK's formal RTGS-like romanization output and generates plausible
informal romanization variants using rule-based transformations.

The generator is:
- **Deterministic:** same input + config produces the same output
- **Configurable:** each transformation rule can be toggled independently
- **Syllable-aware:** uses TLTK's IPA and g2p output to determine vowel length

Design:
    1. Parse TLTK's g2p output to get per-syllable phonetic info
    2. Align TLTK's th2roman output with syllable boundaries
    3. Apply syllable-level transformations based on phonetic properties
    4. Combine syllable variants via Cartesian product
    5. Deduplicate and return sorted list

Five transformation rules:
    - **Vowel lengthening:** long vowels get doubled spellings (di → dee/dii)
    - **Final consonant softening:** voiceless stops become voiced (sawat → sawad)
    - **Cluster simplification:** aspirated clusters simplified (kh → k, th → t)
    - **R-dropping:** r removed from clusters (kr → k, khr → kh)
    - **Initial voicing:** k → g for ก-initial words (kin → gin)

Usage:
    >>> from src.variant_generator import generate_word_variants
    >>> generate_word_variants("สวัสดี")
    ['sawaddee', 'sawatdee', 'sawatdii', ...]

    CLI:
    $ python -m src.variant_generator สวัสดี ครับ
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from itertools import product
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tltk
except ImportError as e:
    raise ImportError(
        "TLTK is required for the variant generator. "
        "Install it with: pip install tltk"
    ) from e


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class VariantConfig:
    """Configuration for which transformation rules are active.

    Attributes:
        vowel_lengthening: Generate doubled-vowel variants for long Thai vowels
            (e.g., di → dee/dii). Affects ~56% of words.
        final_consonant_softening: Soften voiceless final stops to voiced
            (e.g., sawat → sawad, khrap → khrab). Affects ~35% of words.
        cluster_simplification: Simplify aspirated initial clusters
            (e.g., kh → k, th → t, ph → p). Affects ~44% of words.
        r_dropping: Drop 'r' from initial consonant clusters
            (e.g., kr → k, khr → kh). Affects ~10% of words.
        initial_voicing: Voice initial 'k' to 'g' for ก-initial words
            (e.g., kin → gin). Affects ~15% of words.
        max_variants_per_word: Maximum number of variants to return per word.
            The base TLTK romanization is always included. Defaults to 20
            per Research 002 recommendation for production use.
    """

    vowel_lengthening: bool = True
    final_consonant_softening: bool = True
    cluster_simplification: bool = True
    r_dropping: bool = True
    initial_voicing: bool = True
    max_variants_per_word: int = 20


DEFAULT_CONFIG = VariantConfig()


# ---------------------------------------------------------------------------
# Phonetic analysis helpers
# ---------------------------------------------------------------------------


@dataclass
class SyllableInfo:
    """Phonetic information about a single syllable.

    Attributes:
        thai_text: Thai text of this syllable (e.g., "สวัส").
        romanization: RTGS-like romanization from th2roman (e.g., "sawat").
        ipa: IPA transcription from th2ipa (e.g., "sa2.wat2").
        g2p_group: Full g2p group string (e.g., "sa1'wat1").
        has_long_vowel: True if IPA/g2p indicates a long vowel.
        is_open_syllable: True if no final consonant.
        final_consonant: Final consonant string (e.g., "t", "ng", or "").
        initial_cluster: Initial consonant cluster (e.g., "kh", "kr", "k").
        vowel_nucleus: Vowel part between initial and final (e.g., "a", "oo").
    """

    thai_text: str
    romanization: str
    ipa: str = ""
    g2p_group: str = ""
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

    TLTK g2p format example::

        สวัส~ดี<tr/>sa1'wat1~dii0|<s/>

    Returns:
        List of per-syllable g2p groups, e.g. ``["sa1'wat1", "dii0"]``.
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
    """Convert a g2p group to approximate RTGS romanization length.

    Used to estimate per-syllable character counts for splitting
    the whole-word romanization into syllable-level pieces.
    """
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
    """Split the whole-word romanization into per-syllable pieces.

    Strategy: Convert each g2p group to an approximate RTGS romanization
    to estimate the character length of each syllable. Then split the
    romanization string at those boundaries, using a heuristic to prefer
    split points where the next character is a consonant (syllable onset).
    The last syllable always gets whatever remains.

    Args:
        romanization: Full romanized word string.
        g2p_groups: Per-syllable g2p group strings from TLTK.

    Returns:
        List of romanization strings, one per syllable.
    """
    if len(g2p_groups) <= 1:
        return [romanization]

    result: list[str] = []
    remaining = romanization

    for i, group in enumerate(g2p_groups):
        if i == len(g2p_groups) - 1:
            result.append(remaining)
            break

        approx = _g2p_group_to_approx_roman(group)
        approx_len = len(approx)

        if 0 < approx_len <= len(remaining):
            best_len = _find_syllable_boundary(remaining, approx_len)
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


def _find_syllable_boundary(remaining: str, approx_len: int) -> int:
    """Find the best character position to split a syllable boundary.

    Tries the approximate length first, then offsets of ±1 and ±2 characters.
    Prefers split points where the next character is a consonant (indicating
    the start of the next syllable). Falls back to the approximate length.
    """
    for delta in [0, 1, -1, 2, -2]:
        test_len = approx_len + delta
        if 0 < test_len < len(remaining):
            next_char = remaining[test_len]
            if next_char not in "aeiou":
                return test_len
    return approx_len


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
    """Analyze a Thai word using TLTK to get syllable-level phonetic info.

    Calls TLTK's romanization, IPA, g2p, and syllable segmentation APIs,
    then aligns the outputs to produce per-syllable phonetic information.

    Args:
        thai_word: A Thai word string.

    Returns:
        List of :class:`SyllableInfo` objects, one per syllable.
        Returns an empty list if TLTK produces no usable output.
    """
    try:
        roman_raw = tltk.nlp.th2roman(thai_word)
        ipa_raw = tltk.nlp.th2ipa(thai_word)
        g2p_raw = tltk.nlp.g2p(thai_word)
        syl_raw = tltk.nlp.syl_segment(thai_word)
    except Exception:
        logger.warning("TLTK failed to process word: %s", thai_word)
        return []

    roman = _clean_tltk_output(roman_raw)
    ipa = _clean_tltk_output(ipa_raw)

    if not roman:
        logger.warning("TLTK returned empty romanization for: %s", thai_word)
        return []

    thai_syllables = [s for s in _clean_tltk_output(syl_raw).split("~") if s]
    ipa_syllables = [s.strip() for s in ipa.split(".") if s.strip()]
    g2p_groups = _parse_g2p_groups(g2p_raw)
    syl_romans = _split_romanization_by_g2p(roman, g2p_groups)

    syllable_infos: list[SyllableInfo] = []
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

    Returns a sorted list of possible initial clusters including the original.
    """
    cluster = syl.initial_cluster
    if not cluster:
        return [""]

    variants: set[str] = {cluster}

    if config.cluster_simplification:
        simplification: dict[str, list[str]] = {
            "kh": ["k"], "th": ["t"], "ph": ["p"], "ch": ["j", "c"],
        }
        if cluster in simplification:
            variants.update(simplification[cluster])

        three_char: dict[str, list[str]] = {
            "khr": ["kr"], "thr": ["tr"], "phr": ["pr"],
        }
        if cluster in three_char:
            variants.update(three_char[cluster])

    if config.r_dropping:
        r_drop: dict[str, list[str]] = {
            "kr": ["k"], "khr": ["kh", "k"],
            "pr": ["p"], "phr": ["ph", "p"],
            "tr": ["t"], "thr": ["th", "t"],
            "fr": ["f"],
        }
        if cluster in r_drop:
            variants.update(r_drop[cluster])

    if config.initial_voicing:
        voicing: dict[str, list[str]] = {"k": ["g"]}
        if cluster in voicing:
            variants.update(voicing[cluster])

    return sorted(variants)


def _get_vowel_variants(
    syl: SyllableInfo,
    config: VariantConfig,
) -> list[str]:
    """Get all vowel-nucleus variants for a syllable.

    Returns a sorted list of possible vowel nuclei including the original.
    """
    vowel = syl.vowel_nucleus
    if not vowel:
        return [""]

    variants: set[str] = {vowel}

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

    Returns a sorted list of possible final consonants including the original.
    """
    fc = syl.final_consonant
    if not fc:
        return [""]

    variants: set[str] = {fc}

    if config.final_consonant_softening:
        softening: dict[str, str] = {"t": "d", "p": "b", "k": "g"}
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
    (initial variant x vowel variant x final variant) produces one syllable
    variant.

    Args:
        syl: Syllable phonetic information.
        config: Variant generation configuration.

    Returns:
        Sorted list of variant romanizations (excluding the base form).
    """
    initials = _get_initial_variants(syl, config)
    vowels = _get_vowel_variants(syl, config)
    finals = _get_final_variants(syl, config)

    all_variants: set[str] = set()
    for init, vow, fin in product(initials, vowels, finals):
        all_variants.add(init + vow + fin)

    # Remove the base form — it's added separately by generate_word_variants
    all_variants.discard(syl.romanization)

    return sorted(all_variants)


def generate_word_variants(
    thai_word: str,
    config: VariantConfig = DEFAULT_CONFIG,
) -> list[str]:
    """Generate informal romanization variants for a Thai word.

    This is the primary public API. Takes a Thai word string and returns
    all plausible informal romanization variants, including the base TLTK
    romanization.

    Args:
        thai_word: A Thai word string (e.g., "สวัสดี").
        config: Variant generation configuration. Uses :data:`DEFAULT_CONFIG`
            if not specified.

    Returns:
        A sorted, deduplicated list of romanization variants. The base TLTK
        romanization is always included. Returns an empty list if TLTK
        cannot romanize the word.

    Examples:
        >>> variants = generate_word_variants("ดี")
        >>> "di" in variants  # base form
        True
        >>> "dee" in variants  # vowel lengthening
        True
    """
    try:
        base_roman = _clean_tltk_output(tltk.nlp.th2roman(thai_word))
    except Exception:
        logger.warning("TLTK failed to romanize word: %s", thai_word)
        return []

    if not base_roman:
        logger.warning("TLTK returned empty romanization for: %s", thai_word)
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
        # Always keep the base form; trim the rest
        result = [base_roman] + [
            v for v in result if v != base_roman
        ][: config.max_variants_per_word - 1]
        result.sort()

    return result


def generate_variants_for_wordlist(
    thai_words: list[str],
    config: VariantConfig = DEFAULT_CONFIG,
) -> dict[str, list[str]]:
    """Generate variants for a list of Thai words.

    Args:
        thai_words: List of Thai word strings.
        config: Variant generation configuration.

    Returns:
        Dictionary mapping each Thai word to its list of romanization variants.
    """
    return {word: generate_word_variants(word, config) for word in thai_words}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> None:
    """CLI entry point for quick testing.

    Usage::

        python -m src.variant_generator สวัสดี ครับ หมู
        python -m src.variant_generator --max-variants 10 สวัสดี
    """
    args = argv if argv is not None else sys.argv[1:]

    # Simple argument parsing
    config = VariantConfig()
    words: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--max-variants" and i + 1 < len(args):
            config.max_variants_per_word = int(args[i + 1])
            i += 2
        elif args[i] == "--no-vowel-lengthening":
            config.vowel_lengthening = False
            i += 1
        elif args[i] == "--no-final-softening":
            config.final_consonant_softening = False
            i += 1
        elif args[i] == "--no-cluster-simplification":
            config.cluster_simplification = False
            i += 1
        elif args[i] == "--no-r-dropping":
            config.r_dropping = False
            i += 1
        elif args[i] == "--no-initial-voicing":
            config.initial_voicing = False
            i += 1
        elif args[i] == "--help" or args[i] == "-h":
            print("Usage: python -m src.variant_generator [OPTIONS] WORD [WORD ...]")
            print()
            print("Generate informal romanization variants for Thai words.")
            print()
            print("Options:")
            print("  --max-variants N          Max variants per word (default: 20)")
            print("  --no-vowel-lengthening    Disable vowel lengthening rule")
            print("  --no-final-softening      Disable final consonant softening")
            print("  --no-cluster-simplification  Disable cluster simplification")
            print("  --no-r-dropping           Disable r-dropping rule")
            print("  --no-initial-voicing      Disable initial voicing rule")
            print("  -h, --help                Show this help message")
            return
        else:
            words.append(args[i])
            i += 1

    if not words:
        print("Usage: python -m src.variant_generator [OPTIONS] WORD [WORD ...]")
        print("Try --help for more information.")
        sys.exit(1)

    for word in words:
        variants = generate_word_variants(word, config)
        print(f"{word}: {len(variants)} variants")
        for v in variants:
            print(f"  {v}")
        print()


if __name__ == "__main__":
    main()
