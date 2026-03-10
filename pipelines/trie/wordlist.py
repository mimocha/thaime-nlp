"""Word list assembly from multiple Thai NLP sources.

Loads vocabulary from available corpora and PyThaiNLP's built-in word list,
computes per-source frequencies, and produces a unified word list with
source provenance.

Each source produces a Counter of {thai_word: raw_count}. These are
normalized to per-source frequency distributions, then merged with equal
weighting into a single frequency-ranked word list.

Usage:
    python -m pipelines.trie.wordlist
    python -m pipelines.trie.wordlist --sources wisesight,wongnai,pythainlp
"""

from __future__ import annotations

import argparse
import bz2
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from pythainlp.tokenize import word_tokenize

from pipelines.trie.config import OUTPUT_DIR, RAW_DATA_DIR, SOURCES

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# ---------------------------------------------------------------------------
# Thai word filtering (shared with benchmark-wordconv pipeline)
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

# Tokens where every character is the same (e.g. ดดด, กกก).
# Legitimate cases like กก, งง, ออ are handled via overrides.
def _is_single_char_repeat(token: str) -> bool:
    return len(set(token)) == 1

# Single consonant + only above/below vowels and marks (no full vowel structure).
# Catches fragments like ก้, ม่, ริ, ดี that are single-consonant tokens with
# sara i/ii (ิ ี), sara ue/uee (ึ ื), mai han akat (ั), pinthu (ฺ),
# and any tone marks / thanthakhat / other marks (U+0E3A-0E3F, U+0E45-0E5F).
# Legitimate words caught by this rule are handled via overrides.
_SINGLE_CONSONANT_FRAGMENT_RE = re.compile(
    r"^[\u0e01-\u0e2e][\u0e31\u0e34\u0e35\u0e36\u0e37\u0e3a-\u0e3f\u0e45-\u0e5f]+$"
)



def _is_valid_thai_word(token: str) -> bool:
    """Check if a token is a valid Thai word for our vocabulary."""
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


def _tokenize_and_filter(text: str) -> list[str]:
    """Tokenize Thai text and filter to valid Thai words."""
    tokens = word_tokenize(text, engine="newmm")
    return [t for t in tokens if _is_valid_thai_word(t)]


# ---------------------------------------------------------------------------
# Corpus readers
# ---------------------------------------------------------------------------


def read_wisesight() -> Counter:
    """Read Wisesight sentiment corpus (social media messages)."""
    corpus_dir = RAW_DATA_DIR / "wisesight"
    counter: Counter = Counter()
    files = ["pos.txt", "neg.txt", "neu.txt", "q.txt"]

    for fname in files:
        fpath = corpus_dir / fname
        if not fpath.exists():
            print(f"    WARNING: {fpath} not found, skipping")
            continue
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()

        desc = f"    {fname}"
        line_iter = _iter_with_progress(lines, desc=desc, unit="line")
        for line in line_iter:
            line = line.strip()
            if line:
                counter.update(_tokenize_and_filter(line))

    return counter


def read_wongnai() -> Counter:
    """Read Wongnai restaurant review corpus."""
    wongnai_file = RAW_DATA_DIR / "wongnai" / "w_review_train.csv"
    counter: Counter = Counter()

    if not wongnai_file.exists():
        print(f"    WARNING: {wongnai_file} not found, skipping")
        return counter

    with open(wongnai_file, encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter=";"))

    desc = "    wongnai"
    row_iter = _iter_with_progress(rows[1:], desc=desc, unit="row")  # skip header
    for row in row_iter:
        if len(row) >= 1:
            counter.update(_tokenize_and_filter(row[0]))

    return counter


def read_prachathai() -> Counter:
    """Read Prachathai 67K news corpus."""
    prachathai_dir = RAW_DATA_DIR / "prachathai" / "data"
    counter: Counter = Counter()
    files = ["train.jsonl", "valid.jsonl", "test.jsonl"]

    for fname in files:
        fpath = prachathai_dir / fname
        if not fpath.exists():
            print(f"    WARNING: {fpath} not found, skipping")
            continue
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()

        desc = f"    {fname}"
        line_iter = _iter_with_progress(lines, desc=desc, unit="article")
        for line in line_iter:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                for field in ("title", "body_text"):
                    text = data.get(field, "")
                    if text:
                        counter.update(_tokenize_and_filter(text))
            except json.JSONDecodeError:
                continue

    return counter


def _detect_mediawiki_namespace(fileobj) -> str:
    """Detect the MediaWiki XML namespace from the root element.

    Reads the first few elements to find the namespace URI, then returns
    it in {uri} format. Falls back to export-0.10 if detection fails.
    """
    fallback = "{http://www.mediawiki.org/xml/export-0.10/}"
    try:
        for event, elem in ET.iterparse(fileobj, events=("start",)):
            # The root <mediawiki> element carries the namespace
            tag = elem.tag
            if tag.startswith("{"):
                ns = tag[: tag.index("}") + 1]
                return ns
            break
    except ET.ParseError:
        pass
    return fallback


def read_thwiki() -> Counter:
    """Read Thai Wikipedia XML dump.

    Supports both uncompressed XML (preferred, faster) and bz2-compressed
    files. Streams the XML, extracts article text from <text> elements,
    applies lightweight wikitext cleanup, then tokenizes.
    """
    wiki_dir = RAW_DATA_DIR / "thwiki"
    xml_path = wiki_dir / "thwiki-latest-pages-articles.xml"
    bz2_path = wiki_dir / "thwiki-latest-pages-articles.xml.bz2"

    # Prefer uncompressed XML (faster to parse)
    if xml_path.exists():
        source_path = xml_path
        open_fn = lambda: open(xml_path, "r", encoding="utf-8")  # noqa: E731
    elif bz2_path.exists():
        source_path = bz2_path
        open_fn = lambda: bz2.open(bz2_path, "rt", encoding="utf-8")  # noqa: E731
    else:
        print(f"    WARNING: No thwiki dump found in {wiki_dir}")
        print(f"    Expected: {xml_path.name} or {bz2_path.name}")
        print(f"    Download with: python -m src.data.download thwiki")
        return Counter()

    counter: Counter = Counter()
    article_count = 0

    print(f"    Streaming from {source_path.name} (this may take a while)...")

    # Auto-detect MediaWiki XML namespace from the root element
    with open_fn() as f:
        ns = _detect_mediawiki_namespace(f)

    with open_fn() as f:
        # Use iterparse to stream without loading full XML into memory
        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            if elem.tag == f"{ns}text":
                text = elem.text
                if text:
                    cleaned = _clean_wikitext(text)
                    if cleaned:
                        counter.update(_tokenize_and_filter(cleaned))
                        article_count += 1
                        if article_count % 10000 == 0:
                            print(
                                f"    Processed {article_count:,} articles, "
                                f"{len(counter):,} unique words so far..."
                            )

                # Free memory — critical for large XML
                elem.clear()

    print(f"    Finished: {article_count:,} articles processed")
    return counter


# Wikitext cleanup patterns (compiled once)
_WIKI_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_WIKI_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")  # non-nested templates
_WIKI_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/>]*/>", re.DOTALL)
_WIKI_HTML = re.compile(r"<[^>]+>")
_WIKI_LINK = re.compile(r"\[\[[^\]]*?\|([^\]]+)\]\]")  # [[target|display]]
_WIKI_LINK_SIMPLE = re.compile(r"\[\[([^\]|]+)\]\]")  # [[target]]
_WIKI_EXT_LINK = re.compile(r"\[https?://[^\]]*\]")
_WIKI_TABLE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_WIKI_HEADER = re.compile(r"^=+.*?=+$", re.MULTILINE)
_WIKI_CATEGORY = re.compile(r"\[\[(?:หมวดหมู่|Category):[^\]]+\]\]")
_WIKI_FILE = re.compile(r"\[\[(?:ไฟล์|File|Image):[^\]]+\]\]")
_WIKI_FORMATTING = re.compile(r"'{2,5}")
_WIKI_BULLET = re.compile(r"^[*#:;]+\s*", re.MULTILINE)


def _clean_wikitext(text: str) -> str:
    """Remove wikitext markup to extract plain text.

    This is a lightweight cleanup — not a full parser. Good enough for
    vocabulary extraction where some noise is acceptable.
    """
    # Remove structural elements first
    text = _WIKI_COMMENT.sub("", text)
    text = _WIKI_TABLE.sub("", text)
    text = _WIKI_REF.sub("", text)
    text = _WIKI_CATEGORY.sub("", text)
    text = _WIKI_FILE.sub("", text)

    # Remove templates (iterate for nested templates)
    for _ in range(5):
        new_text = _WIKI_TEMPLATE.sub("", text)
        if new_text == text:
            break
        text = new_text

    # Convert links to display text
    text = _WIKI_LINK.sub(r"\1", text)
    text = _WIKI_LINK_SIMPLE.sub(r"\1", text)
    text = _WIKI_EXT_LINK.sub("", text)

    # Remove HTML and formatting
    text = _WIKI_HTML.sub("", text)
    text = _WIKI_FORMATTING.sub("", text)
    text = _WIKI_HEADER.sub("", text)
    text = _WIKI_BULLET.sub("", text)

    return text


def read_pythainlp() -> Counter:
    """Load PyThaiNLP's built-in Thai word list.

    Returns a Counter with uniform count of 1 per word (no frequency data).
    """
    from pythainlp.corpus.common import thai_words

    words = thai_words()
    counter: Counter = Counter()
    for word in words:
        if _is_valid_thai_word(word):
            counter[word] = 1

    return counter


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

# Maps source name to its reader function
_SOURCE_READERS: dict[str, callable] = {
    "wisesight": read_wisesight,
    "wongnai": read_wongnai,
    "prachathai": read_prachathai,
    "thwiki": read_thwiki,
    "pythainlp": read_pythainlp,
}


def _check_source_available(name: str) -> bool:
    """Check if a corpus source has data available to read."""
    if name == "pythainlp":
        return True  # Always available (built-in)
    corpus_dir = RAW_DATA_DIR / name
    if name == "thwiki":
        xml_path = corpus_dir / "thwiki-latest-pages-articles.xml"
        bz2_path = corpus_dir / "thwiki-latest-pages-articles.xml.bz2"
        return xml_path.exists() or bz2_path.exists()
    return corpus_dir.exists() and any(corpus_dir.iterdir())


# ---------------------------------------------------------------------------
# Frequency merging
# ---------------------------------------------------------------------------


def normalize_frequencies(counter: Counter) -> dict[str, float]:
    """Normalize raw counts to a frequency distribution summing to 1.0."""
    total = sum(counter.values())
    if total == 0:
        return {}
    return {word: count / total for word, count in counter.items()}


def merge_frequencies(
    freq_dicts: list[dict[str, float]],
) -> dict[str, float]:
    """Merge frequency dicts with equal weighting.

    Each source contributes equally. Words absent from a source get 0
    for that source's contribution.
    """
    if not freq_dicts:
        return {}

    weight = 1.0 / len(freq_dicts)
    merged: dict[str, float] = {}
    all_words: set[str] = set()
    for fd in freq_dicts:
        all_words.update(fd.keys())

    for word in all_words:
        score = sum(fd.get(word, 0.0) * weight for fd in freq_dicts)
        merged[word] = score

    return merged


# ---------------------------------------------------------------------------
# Word list data structure
# ---------------------------------------------------------------------------


class WordEntry:
    """A word in the assembled word list."""

    __slots__ = ("word", "frequency", "sources")

    def __init__(self, word: str, frequency: float, sources: set[str]):
        self.word = word
        self.frequency = frequency
        self.sources = sources


# ---------------------------------------------------------------------------
# Compound phrase decomposition
# ---------------------------------------------------------------------------

# Minimum character length to consider a word for decomposition.
_DECOMPOSE_MIN_CHARS = 10

# Minimum character length for each part in a decomposition. Prevents
# spurious splits into tiny fragments (e.g. ประชาธิปไตย -> ประชา+ธิปไ+ตย).
_DECOMPOSE_MIN_PART_CHARS = 3


def _greedy_decompose(
    word: str, vocab: set[str], min_part_len: int = _DECOMPOSE_MIN_PART_CHARS,
) -> list[str] | None:
    """Try to split a word into known vocab entries using greedy longest-match.

    Returns a list of parts if the entire word can be covered by 2+ vocab
    entries (each >= min_part_len chars, each shorter than the original word).
    Returns None if decomposition fails.
    """
    parts: list[str] = []
    i = 0
    while i < len(word):
        found = False
        for end in range(len(word), i, -1):
            candidate = word[i:end]
            if len(candidate) < min_part_len:
                continue
            if candidate == word:
                continue
            if candidate in vocab:
                parts.append(candidate)
                i = end
                found = True
                break
        if not found:
            return None
    return parts if len(parts) >= 2 else None


def _decompose_compounds(
    entries: list[WordEntry],
) -> list[WordEntry]:
    """Decompose compound phrases whose sub-words already exist in the list.

    Long words (>= _DECOMPOSE_MIN_CHARS) are split using greedy longest-match
    against the existing vocabulary. If the entire word can be covered by 2+
    known shorter words, the compound is redundant and is removed. Its
    frequency is distributed equally to the sub-tokens, and its source
    provenance is merged.

    This prevents multi-word expressions (e.g. เจ้าหน้าที่ตำรวจ) from
    reaching the variant generator where they trigger exponential Cartesian
    products across many syllables.

    Words that don't fully decompose into known sub-tokens are kept as-is
    (e.g. ประชาธิปไตย — can't be split into meaningful known words).
    """
    vocab = {e.word for e in entries}

    to_remove: set[str] = set()
    # Track frequency/source additions for sub-tokens
    freq_additions: dict[str, float] = {}
    source_additions: dict[str, set[str]] = {}

    for entry in entries:
        if len(entry.word) < _DECOMPOSE_MIN_CHARS:
            continue

        parts = _greedy_decompose(entry.word, vocab)
        if parts is None:
            continue

        # This compound is redundant — mark for removal
        to_remove.add(entry.word)

        # Distribute frequency equally to sub-tokens
        share = entry.frequency / len(parts)
        for t in parts:
            freq_additions[t] = freq_additions.get(t, 0.0) + share
            if t not in source_additions:
                source_additions[t] = set()
            source_additions[t].update(entry.sources)

    if not to_remove:
        return entries

    # Apply changes
    new_entries: list[WordEntry] = []
    for entry in entries:
        if entry.word in to_remove:
            continue
        # Add redistributed frequency and sources
        if entry.word in freq_additions:
            entry.frequency += freq_additions[entry.word]
            entry.sources.update(source_additions[entry.word])
        new_entries.append(entry)

    # Re-sort by frequency
    new_entries.sort(key=lambda e: e.frequency, reverse=True)

    print(f"\n  Compound decomposition:")
    print(f"    Phrases decomposed: {len(to_remove):,}")
    print(f"    Words after decomposition: {len(new_entries):,}")

    return new_entries


def assemble_wordlist(
    sources: dict[str, bool] | None = None,
) -> list[WordEntry]:
    """Assemble the unified word list from all enabled sources.

    Args:
        sources: Dict of {source_name: enabled}. Defaults to config.SOURCES.

    Returns:
        List of WordEntry, sorted by frequency descending.
    """
    if sources is None:
        sources = SOURCES

    enabled = {name for name, on in sources.items() if on}

    # Read each source
    raw_counters: dict[str, Counter] = {}
    for name in sorted(enabled):
        reader = _SOURCE_READERS.get(name)
        if reader is None:
            print(f"  WARNING: No reader for source '{name}', skipping")
            continue

        if not _check_source_available(name):
            print(f"  [{name}] Not available (not downloaded), skipping")
            continue

        print(f"  [{name}] Reading...")
        counter = reader()
        raw_counters[name] = counter
        print(
            f"  [{name}] {len(counter):,} unique words, "
            f"{sum(counter.values()):,} total tokens"
        )

    if not raw_counters:
        print("  ERROR: No sources loaded!")
        return []

    # Normalize each source
    norm_freqs = {
        name: normalize_frequencies(counter)
        for name, counter in raw_counters.items()
    }

    # Merge with equal weights
    merged = merge_frequencies(list(norm_freqs.values()))

    # Build word entries with source provenance
    entries: list[WordEntry] = []
    for word, freq in merged.items():
        word_sources = {
            name for name, counter in raw_counters.items() if word in counter
        }
        entries.append(WordEntry(word=word, frequency=freq, sources=word_sources))

    # Sort by frequency descending
    entries.sort(key=lambda e: e.frequency, reverse=True)

    # Decompose compound phrases into base vocabulary
    entries = _decompose_compounds(entries)

    # Print summary
    source_names = sorted(raw_counters.keys())
    print(f"\n  Assembled word list:")
    print(f"    Total unique words: {len(entries):,}")
    print(f"    Sources loaded: {', '.join(source_names)}")

    _print_source_stats(entries, source_names)

    return entries


def _print_source_stats(entries: list[WordEntry], source_names: list[str]) -> None:
    """Print per-source overlap and unique word statistics."""
    total = len(entries)
    if total == 0:
        return

    print(f"\n    Per-source statistics:")
    for name in source_names:
        in_source = sum(1 for e in entries if name in e.sources)
        unique = sum(
            1 for e in entries
            if e.sources == {name}
        )
        print(
            f"      {name:<14} {in_source:>8,} words "
            f"({in_source * 100 / total:5.1f}%), "
            f"{unique:>7,} unique to this source"
        )

    # Distribution by number of sources
    from collections import Counter as C
    source_count_dist = C(len(e.sources) for e in entries)
    print(f"\n    Words by source count:")
    for n in sorted(source_count_dist):
        count = source_count_dist[n]
        print(f"      In {n} source(s): {count:>8,} ({count * 100 / total:5.1f}%)")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _iter_with_progress(iterable, desc="", unit="it"):
    """Wrap an iterable with tqdm progress bar if available."""
    if tqdm is not None:
        return tqdm(iterable, desc=desc, unit=unit, leave=False)
    return iterable


def save_wordlist_csv(entries: list[WordEntry], path: Path) -> None:
    """Save the word list to CSV for inspection.

    Columns: rank, thai_word, frequency, source_count, sources
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "thai_word", "frequency", "source_count", "sources"])
        for i, entry in enumerate(entries):
            writer.writerow([
                i + 1,
                entry.word,
                f"{entry.frequency:.12f}",
                len(entry.sources),
                "|".join(sorted(entry.sources)),
            ])
    print(f"  Word list saved to {path} ({len(entries):,} entries)")


def load_wordlist_csv(path: Path) -> list[WordEntry]:
    """Load a previously saved word list from CSV.

    Returns:
        List of WordEntry, in the same order as saved (frequency descending).
    """
    entries: list[WordEntry] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(WordEntry(
                word=row["thai_word"],
                frequency=float(row["frequency"]),
                sources=set(row["sources"].split("|")) if row["sources"] else set(),
            ))
    return entries


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble Thai word list from multiple sources."
    )
    parser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="Comma-separated list of sources to enable (default: all configured)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: outputs/wordlist.csv)",
    )
    args = parser.parse_args()

    # Parse sources
    sources = dict(SOURCES)
    if args.sources:
        # Disable all, then enable only specified
        sources = {name: False for name in sources}
        for name in args.sources.split(","):
            name = name.strip()
            if name in sources:
                sources[name] = True
            else:
                print(f"WARNING: Unknown source '{name}', skipping")

    output_path = Path(args.output) if args.output else OUTPUT_DIR / "wordlist.csv"

    print("=" * 60)
    print("Word List Assembly")
    print("=" * 60)

    entries = assemble_wordlist(sources=sources)
    if entries:
        save_wordlist_csv(entries, output_path)

    print("\nDone!")


if __name__ == "__main__":
    main()
