"""Dictionary-driven Thai Romanization Variant Generator (v2).

Takes a Thai word and generates all plausible informal romanization
variants using a component-level dictionary that maps phonological
components (onsets, vowels, codas) to their valid Latin spellings.

The generator:
- Uses TLTK g2p output to decompose words into onset/vowel/coda triples
- Looks up each component in the dictionary for valid variants
- Produces whole-word variants via Cartesian product of component variants
- Is deterministic: same input produces the same output

No hardcoded transformation rules — the dictionary is the single source
of truth.

Usage:
    >>> from src.variant_generator import generate_word_variants
    >>> generate_word_variants("สวัสดี")
    ['sawaddee', 'sawatdee', ...]

    CLI:
    $ python -m src.variant_generator สวัสดี ครับ
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

try:
    import tltk
except ImportError as e:
    raise ImportError(
        "TLTK is required for the variant generator. "
        "Install it with: pip install tltk"
    ) from e


# ---------------------------------------------------------------------------
# Dictionary loading
# ---------------------------------------------------------------------------

# Path to the component romanization dictionary
_DICT_PATH = (
    Path(__file__).parent.parent / "data" / "dictionaries"
    / "component-romanization.yaml"
)

# Module-level cache for the loaded dictionary
_cached_dictionary: Optional[dict] = None


def load_component_dictionary(path: Optional[Path] = None) -> dict:
    """Load the component romanization dictionary from YAML.

    Returns a dict with keys ``"onsets"``, ``"vowels"``, ``"codas"``.
    Each maps g2p phoneme strings to lists of variant romanizations.

    Example::

        {
            "onsets": {"k": ["k", "g"], "kh": ["kh", "k"], ...},
            "vowels": {"a": ["a", "u", "ah"], "aa": ["a", "aa", "ar", "ah"], ...},
            "codas": {"n": ["n"], "t": ["t", "d"], ...},
        }
    """
    global _cached_dictionary
    if _cached_dictionary is not None and path is None:
        return _cached_dictionary

    dict_path = path or _DICT_PATH
    with open(dict_path) as f:
        raw = yaml.safe_load(f)

    result: dict[str, dict[str, list[str]]] = {
        "onsets": {},
        "vowels": {},
        "codas": {},
    }

    for _key, entry in raw.get("onsets", {}).items():
        g2p_key = entry["g2p"]
        result["onsets"][g2p_key] = entry["variants"]

    for _key, entry in raw.get("vowels", {}).items():
        g2p_key = entry["g2p"]
        result["vowels"][g2p_key] = entry["variants"]

    for _key, entry in raw.get("codas", {}).items():
        g2p_key = entry["g2p"]
        result["codas"][g2p_key] = entry["variants"]

    if path is None:
        _cached_dictionary = result

    return result


def _get_dictionary() -> dict:
    """Get the cached component dictionary, loading if needed."""
    return load_component_dictionary()


# ---------------------------------------------------------------------------
# G2P parsing
# ---------------------------------------------------------------------------

# All possible g2p onset strings, ordered longest-first for greedy matching.
# This list covers all Thai initial consonants and clusters as represented
# by TLTK's g2p output.
_G2P_ONSETS = [
    # 3-char clusters
    "khr", "khw", "khl", "phr", "phl", "thr",
    # 2-char clusters and digraphs
    "kh", "kr", "kl", "kw", "ch", "th", "tr",
    "ph", "pr", "pl", "bl", "fr", "fl",
    # 1-char consonants
    "k", "N", "c", "d", "t", "n", "b", "p", "f", "m",
    "j", "r", "l", "w", "h", "s", "?",
]

# All possible g2p coda consonants
_G2P_CODAS = ["N", "ng", "n", "m", "t", "c", "k", "p", "w", "j"]

# Aliases for vowel g2p patterns that TLTK produces but differ from
# our dictionary keys. Maps TLTK long-form diphthongs -> dictionary key.
_VOWEL_ALIASES: dict[str, str] = {
    "uua": "ua",      # อัว — TLTK doubles the u for long form
    "OOj": "Oj",      # โอย — TLTK doubles the O for long form
    "uuaj": "uaj",    # อวย — TLTK doubles the u for long form
}


@dataclass
class SyllableComponents:
    """Decomposed phonological syllable from g2p parsing.

    Attributes:
        onset: g2p onset string (e.g., "kh", "c", "?", "")
        vowel: g2p vowel string, resolved to dictionary key
            (e.g., "aa", "aj", "OO")
        coda: g2p coda string (e.g., "n", "t", "", "w")
        tone: tone number string (e.g., "0", "1", "2")
        thai_segment: Thai text of the parent syllable segment
    """

    onset: str
    vowel: str
    coda: str
    tone: str = ""
    thai_segment: str = ""


def _clean_tltk_output(s: str) -> str:
    """Remove TLTK markup tags from output."""
    return re.sub(r"<[^>]+>", "", s).strip()


def _extract_g2p_transliteration(g2p_raw: str) -> str:
    """Extract the transliteration string from raw g2p output.

    TLTK g2p format: ``Thai~text<tr/>g2p_data|<s/>``

    Returns the g2p_data part, e.g. ``"sa1'wat1~dii0"``.
    """
    match = re.search(r"<tr/>([^<|]+)", g2p_raw)
    if not match:
        return ""
    return match.group(1).strip()


def _split_g2p_into_syllables(g2p_trans: str) -> list[str]:
    """Split g2p transliteration into individual syllable strings.

    Both ``~`` (Thai syllable boundary) and ``'`` (sub-syllable boundary)
    are treated as separators.

    Example::

        "sa1'wat1~dii0" -> ["sa1", "wat1", "dii0"]
    """
    return [s for s in re.split(r"[~']", g2p_trans) if s]


def _parse_g2p_syllable(g2p_syl: str, dictionary: dict) -> SyllableComponents:
    """Parse a single g2p syllable string into onset/vowel/coda components.

    Strategy:
        1. Strip tone number (last character if digit)
        2. Greedy longest-prefix match for onset
        3. Try each possible coda suffix; accept when remainder is a known vowel
        4. Vowel aliases handle TLTK's long-form diphthong representations

    Args:
        g2p_syl: Single g2p syllable string (e.g., ``"khaaw2"``, ``"dii0"``).
        dictionary: Component dictionary with ``"vowels"`` key for validation.

    Returns:
        SyllableComponents with parsed onset, vowel, coda, and tone.
    """
    # 1. Strip tone number
    tone = ""
    s = g2p_syl
    if s and s[-1].isdigit():
        tone = s[-1]
        s = s[:-1]

    if not s:
        return SyllableComponents(onset="", vowel="", coda="", tone=tone)

    # 2. Greedy onset match (longest first)
    onset = ""
    for candidate in _G2P_ONSETS:
        if s.startswith(candidate):
            onset = candidate
            break

    remainder = s[len(onset):]

    if not remainder:
        # Edge case: syllable is just an onset (shouldn't normally happen)
        return SyllableComponents(onset=onset, vowel="", coda="", tone=tone)

    # 3. Try coda suffixes to find a valid vowel
    known_vowels = set(dictionary.get("vowels", {}).keys())

    # Try: no coda first (favors diphthongs), then each possible coda
    coda_candidates = [""] + _G2P_CODAS

    for coda in coda_candidates:
        if coda and not remainder.endswith(coda):
            continue

        if coda:
            vowel_part = remainder[: -len(coda)]
        else:
            vowel_part = remainder

        if not vowel_part:
            continue

        # Check if vowel_part is a known vowel or alias
        resolved_vowel = _VOWEL_ALIASES.get(vowel_part, vowel_part)
        if resolved_vowel in known_vowels:
            return SyllableComponents(
                onset=onset, vowel=resolved_vowel, coda=coda, tone=tone,
            )

    # 4. Fallback: treat entire remainder as vowel (unrecognized)
    logger.debug(
        "Unrecognized vowel pattern %r in g2p syllable %r",
        remainder, g2p_syl,
    )
    return SyllableComponents(onset=onset, vowel=remainder, coda="", tone=tone)


# ---------------------------------------------------------------------------
# Thai text inspection
# ---------------------------------------------------------------------------


def _detect_hor_nam(thai_segment: str) -> Optional[str]:
    """Detect หน (hor-nam) or หม (hor-nam) onset in Thai text.

    TLTK g2p doesn't distinguish หน/หม from น/ม — both produce ``n``/``m``.
    We detect these from the Thai text to use the ``nh``/``mh`` dictionary
    entries, which carry additional spelling variants (e.g., nha, mhoo).

    Returns:
        ``"nh"`` if หน detected, ``"mh"`` if หม detected, ``None`` otherwise.
    """
    if not thai_segment:
        return None

    # Extract base consonants only (skip Thai combining marks and leading vowels).
    # Thai combining characters: U+0E31..U+0E3A (above/below vowels)
    # and U+0E47..U+0E4E (tone marks, thanthakhat, etc.)
    # Thai leading vowels (written before consonant): เ แ โ ใ ไ
    _leading_vowels = {0x0E40, 0x0E41, 0x0E42, 0x0E43, 0x0E44}
    base_chars: list[str] = []
    for ch in thai_segment:
        cp = ord(ch)
        if cp in _leading_vowels:
            continue  # Skip leading vowels
        if not (0x0E31 <= cp <= 0x0E3A or 0x0E47 <= cp <= 0x0E4E):
            base_chars.append(ch)
        if len(base_chars) >= 2:
            break

    if len(base_chars) >= 2 and base_chars[0] == "\u0e2b":  # ห
        if base_chars[1] == "\u0e19":  # น
            return "nh"
        if base_chars[1] == "\u0e21":  # ม
            return "mh"

    return None


def _detect_jor_coda(thai_segment: str) -> bool:
    """Detect if the syllable's coda consonant is จ (U+0E08).

    TLTK g2p maps จ-as-coda to ``t``, but we have a separate ``c`` coda
    entry with additional variants (j, d). This function detects จ from
    the Thai text so we can use the correct dictionary key.

    Returns:
        ``True`` if the last Thai consonant in the segment is จ.
    """
    if not thai_segment:
        return False

    # Find the last Thai consonant (ก U+0E01 through ฮ U+0E2E)
    last_consonant = None
    for ch in thai_segment:
        if 0x0E01 <= ord(ch) <= 0x0E2E:
            last_consonant = ch

    return last_consonant == "\u0e08"  # จ


# ---------------------------------------------------------------------------
# Word analysis
# ---------------------------------------------------------------------------


def analyze_word(thai_word: str) -> list[SyllableComponents]:
    """Analyze a Thai word into syllable components using TLTK g2p.

    Calls TLTK's g2p and syl_segment APIs, parses the g2p output into
    onset/vowel/coda triples per phonological syllable, and applies
    Thai-text-based corrections (e.g., หน/หม detection).

    Args:
        thai_word: A Thai word string.

    Returns:
        List of :class:`SyllableComponents`, one per phonological syllable.
        Returns an empty list if TLTK produces no usable output.
    """
    try:
        g2p_raw = tltk.nlp.g2p(thai_word)
        syl_raw = tltk.nlp.syl_segment(thai_word)
    except Exception:
        logger.warning("TLTK failed to process word: %s", thai_word)
        return []

    g2p_trans = _extract_g2p_transliteration(g2p_raw)
    if not g2p_trans:
        logger.warning("TLTK returned empty g2p for: %s", thai_word)
        return []

    dictionary = _get_dictionary()

    # Parse Thai syllable segments (~ separated)
    thai_segments = [
        s for s in _clean_tltk_output(syl_raw).split("~") if s
    ]

    # Parse g2p: first split by ~ to align with Thai segments
    g2p_segment_groups = [g for g in g2p_trans.split("~") if g]

    syllables: list[SyllableComponents] = []

    for seg_idx, g2p_group in enumerate(g2p_segment_groups):
        thai_seg = (
            thai_segments[seg_idx] if seg_idx < len(thai_segments) else ""
        )

        # Split sub-syllables within this group (separated by ')
        sub_syllables = [s for s in g2p_group.split("'") if s]

        for sub_idx, g2p_syl in enumerate(sub_syllables):
            comp = _parse_g2p_syllable(g2p_syl, dictionary)
            comp.thai_segment = thai_seg

            # Apply หน/หม correction for the first sub-syllable
            if sub_idx == 0:
                hor_nam = _detect_hor_nam(thai_seg)
                if hor_nam and comp.onset in ("n", "m"):
                    comp.onset = hor_nam

            # Apply จ-as-coda correction (TLTK maps จ coda to 't')
            if comp.coda == "t" and _detect_jor_coda(thai_seg):
                comp.coda = "c"

            syllables.append(comp)

    return syllables


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------


def generate_syllable_variants(comp: SyllableComponents) -> list[str]:
    """Generate all romanization variants for a single syllable.

    Looks up each component (onset, vowel, coda) in the dictionary and
    returns the Cartesian product of all variant combinations.

    Args:
        comp: Parsed syllable components.

    Returns:
        Sorted, deduplicated list of variant romanizations for this syllable.
    """
    dictionary = _get_dictionary()

    # Look up onset variants
    onset_variants = dictionary["onsets"].get(comp.onset, None)
    if onset_variants is None:
        if comp.onset in ("?", ""):
            onset_variants = [""]  # Zero onset
        else:
            logger.debug("Unknown onset %r, using as-is", comp.onset)
            onset_variants = [comp.onset]

    # Look up vowel variants
    vowel_variants = dictionary["vowels"].get(comp.vowel, None)
    if vowel_variants is None:
        if comp.vowel:
            logger.debug("Unknown vowel %r, using as-is", comp.vowel)
            vowel_variants = [comp.vowel]
        else:
            vowel_variants = [""]

    # Guard: short "a" → "u" only valid in closed syllables (with coda).
    # In open syllables (จะ, นะ, ค่ะ), "u" produces implausible forms.
    if comp.vowel == "a" and not comp.coda and "u" in vowel_variants:
        vowel_variants = [v for v in vowel_variants if v != "u"]

    # Look up coda variants
    coda_variants = dictionary["codas"].get(comp.coda, None)
    if coda_variants is None:
        if comp.coda:
            logger.debug("Unknown coda %r, using as-is", comp.coda)
            coda_variants = [comp.coda]
        else:
            coda_variants = [""]

    # Cartesian product
    all_variants: set[str] = set()
    for o, v, c in product(onset_variants, vowel_variants, coda_variants):
        all_variants.add(o + v + c)

    return sorted(all_variants)


def generate_word_variants(
    thai_word: str,
    max_variants: int = 20,
) -> list[str]:
    """Generate informal romanization variants for a Thai word.

    Primary public API. Takes a Thai word and returns all plausible
    informal romanization variants using the component dictionary.

    Args:
        thai_word: A Thai word string (e.g., "สวัสดี").
        max_variants: Maximum number of variants to return (default: 20).

    Returns:
        A sorted, deduplicated list of romanization variants. The base TLTK
        romanization is always included. Returns an empty list if TLTK
        cannot process the word.

    Examples:
        >>> variants = generate_word_variants("ดี")
        >>> "di" in variants
        True
        >>> "dee" in variants
        True
    """
    # Get the base TLTK romanization as fallback
    try:
        base_roman = _clean_tltk_output(tltk.nlp.th2roman(thai_word))
    except Exception:
        logger.warning("TLTK failed to romanize: %s", thai_word)
        return []

    if not base_roman:
        return []

    syllables = analyze_word(thai_word)
    if not syllables:
        return [base_roman]

    # Generate per-syllable variant lists
    syllable_options: list[list[str]] = []
    for comp in syllables:
        syllable_options.append(generate_syllable_variants(comp))

    # Cartesian product across syllables
    all_variants: set[str] = set()
    for combo in product(*syllable_options):
        all_variants.add("".join(combo))

    # Always include the TLTK base romanization
    all_variants.add(base_roman)

    result = sorted(all_variants)

    # Trim to max_variants, always keeping base form
    if len(result) > max_variants:
        result = [base_roman] + [
            v for v in result if v != base_roman
        ][: max_variants - 1]
        result.sort()

    return result


def generate_variants_for_wordlist(
    thai_words: list[str],
    max_variants: int = 20,
) -> dict[str, list[str]]:
    """Generate variants for a list of Thai words.

    Args:
        thai_words: List of Thai word strings.
        max_variants: Maximum variants per word.

    Returns:
        Dictionary mapping each Thai word to its list of romanization variants.
    """
    return {
        word: generate_word_variants(word, max_variants)
        for word in thai_words
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> None:
    """CLI entry point for quick testing.

    Usage::

        python -m src.variant_generator สวัสดี ครับ หมู
        python -m src.variant_generator --max-variants 10 สวัสดี
        python -m src.variant_generator --analyze สวัสดี
    """
    args = argv if argv is not None else sys.argv[1:]

    max_variants = 20
    show_analysis = False
    words: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--max-variants" and i + 1 < len(args):
            max_variants = int(args[i + 1])
            i += 2
        elif args[i] == "--analyze":
            show_analysis = True
            i += 1
        elif args[i] in ("--help", "-h"):
            print("Usage: python -m src.variant_generator [OPTIONS] WORD [WORD ...]")
            print()
            print("Generate informal romanization variants for Thai words.")
            print()
            print("Options:")
            print("  --max-variants N   Max variants per word (default: 20)")
            print("  --analyze          Show g2p decomposition details")
            print("  -h, --help         Show this help message")
            return
        else:
            words.append(args[i])
            i += 1

    if not words:
        print("Usage: python -m src.variant_generator [OPTIONS] WORD [WORD ...]")
        print("Try --help for more information.")
        sys.exit(1)

    for word in words:
        if show_analysis:
            syllables = analyze_word(word)
            print(f"{word}: {len(syllables)} syllables")
            for j, comp in enumerate(syllables):
                print(
                    f"  [{j}] onset={comp.onset!r} vowel={comp.vowel!r} "
                    f"coda={comp.coda!r} tone={comp.tone}"
                )
            print()

        variants = generate_word_variants(word, max_variants)
        print(f"{word}: {len(variants)} variants")
        for v in variants:
            print(f"  {v}")
        print()


if __name__ == "__main__":
    main()
