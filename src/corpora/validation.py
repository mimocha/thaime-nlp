"""Thai word validation heuristics.

Provides ``is_valid_thai_word()`` — the strict filter used across all
pipelines to decide whether a token qualifies as a Thai vocabulary entry.

Extracted from ``pipelines/trie/wordlist.py``.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Matches strings that are purely Thai script (consonants, vowels, tone marks)
_THAI_WORD_RE = re.compile(r"^[\u0e01-\u0e3a\u0e40-\u0e4e]+$")
_MIN_WORD_LEN = 2
_MAX_WORD_LEN = 30

# Mai tri (๊) and mai chattawa (๋) — colloquial/non-standard tone marks.
# TLTK cannot romanize words containing these, so we filter them for now.
_COLLOQUIAL_TONE_MARKS = set("\u0e4a\u0e4b")

# Detects character repeated 4+ times in a row (spam/internet slang).
# Threshold is 4 (not 3) to preserve legitimate compounds like แบบบาง, ครรรภ์.
_REPEATED_CHAR_RE = re.compile(r"(.)\1{3,}")

# Detects maiyamok (ๆ) repetition patterns — sequences of just ๆ
_MAIYAMOK_ONLY_RE = re.compile(r"^[\u0e46]+$")

# Tokens with no Thai consonants (only vowels, tone marks, combining marks).
# Always tokenization artifacts (e.g. าาา, ะะ, ็็).
_NO_CONSONANT_RE = re.compile(r"^[\u0e2f-\u0e5f]+$")

# Single consonant + only above/below vowels and marks (no full vowel structure).
# Catches fragments like ก้, ม่, ริ, ดี that are single-consonant tokens with
# sara i/ii (ิ ี), sara ue/uee (ึ ื), mai han akat (ั), pinthu (ฺ),
# and any tone marks / thanthakhat / other marks (U+0E3A-0E3F, U+0E45-0E5F).
# Legitimate words caught by this rule are handled via overrides.
_SINGLE_CONSONANT_FRAGMENT_RE = re.compile(
    r"^[\u0e01-\u0e2e][\u0e31\u0e34\u0e35\u0e36\u0e37\u0e3a-\u0e3f\u0e45-\u0e5f]+$"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_single_char_repeat(token: str) -> bool:
    """Tokens where every character is the same (e.g. ดดด, กกก).

    Legitimate cases like กก, งง, ออ are handled via overrides.
    """
    return len(set(token)) == 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_valid_thai_word(token: str) -> bool:
    """Check if a token is a valid Thai word for our vocabulary.

    This is the strict filter used by both the trie and n-gram pipelines.
    It rejects:
    - Empty / too-short / too-long tokens
    - Non-Thai-script characters (digits, Latin, punctuation)
    - Maiyamok-only sequences (ๆๆๆ)
    - Tokens starting with ๆ (tokenization artifacts)
    - Spam (4+ consecutive identical characters)
    - Colloquial tone marks (๊, ๋) that TLTK cannot handle
    - Vowel/mark-only sequences (no consonants)
    - Single repeating character tokens
    - Single-consonant + mark fragments
    """
    if not token or len(token) < _MIN_WORD_LEN or len(token) > _MAX_WORD_LEN:
        return False
    if not _THAI_WORD_RE.match(token):
        return False

    # Reject tokens that are just repeated maiyamok (ๆๆๆ)
    if _MAIYAMOK_ONLY_RE.match(token):
        return False

    # Reject tokens starting with ๆ — tokenization artifacts (e.g. ๆคน from จริงๆคน)
    if token.startswith("\u0e46"):
        return False

    # Reject tokens with 4+ consecutive identical characters (spam)
    if _REPEATED_CHAR_RE.search(token):
        return False

    # Reject tokens with colloquial tone marks (๊, ๋) — TLTK can't handle these
    if any(c in _COLLOQUIAL_TONE_MARKS for c in token):
        return False

    # Reject tokens with no Thai consonants (pure vowel/mark sequences)
    if _NO_CONSONANT_RE.fullmatch(token):
        return False

    # Reject single repeating character tokens (e.g. ดดด, กกก, ะะะ)
    if _is_single_char_repeat(token):
        return False

    # Reject single-consonant + mark fragments (e.g. ก้, ม่, ดี, ริ)
    if _SINGLE_CONSONANT_FRAGMENT_RE.fullmatch(token):
        return False

    return True
