"""Word list assembly from multiple Thai NLP sources.

Loads vocabulary from available corpora and PyThaiNLP's built-in word list,
computes per-source frequencies, and produces a unified word list with
source provenance.

Corpus reading, tokenization, and validation are delegated to ``src.corpora``.
This module retains:
- ``WordEntry`` data structure
- Compound phrase decomposition
- Word list assembly orchestration
- CSV I/O helpers
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from pipelines.config import TrieConfig
from pipelines.console import console
from src.corpora.readers import check_corpus_available, read_corpus
from src.utils.frequency import merge_frequencies, normalize_frequencies


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
    """
    vocab = {e.word for e in entries}

    to_remove: set[str] = set()
    freq_additions: dict[str, float] = {}
    source_additions: dict[str, set[str]] = {}

    for entry in entries:
        if len(entry.word) < _DECOMPOSE_MIN_CHARS:
            continue

        parts = _greedy_decompose(entry.word, vocab)
        if parts is None:
            continue

        to_remove.add(entry.word)

        share = entry.frequency / len(parts)
        for t in parts:
            freq_additions[t] = freq_additions.get(t, 0.0) + share
            if t not in source_additions:
                source_additions[t] = set()
            source_additions[t].update(entry.sources)

    if not to_remove:
        return entries

    new_entries: list[WordEntry] = []
    for entry in entries:
        if entry.word in to_remove:
            continue
        if entry.word in freq_additions:
            entry.frequency += freq_additions[entry.word]
            entry.sources.update(source_additions[entry.word])
        new_entries.append(entry)

    new_entries.sort(key=lambda e: e.frequency, reverse=True)

    console.print(f"\n  Compound decomposition:")
    console.print(f"    Phrases decomposed: {len(to_remove):,}")
    console.print(f"    Words after decomposition: {len(new_entries):,}")

    return new_entries


# ---------------------------------------------------------------------------
# Word list assembly
# ---------------------------------------------------------------------------


def assemble_wordlist(
    sources: dict[str, bool] | None = None,
) -> list[WordEntry]:
    """Assemble the unified word list from all enabled sources.

    Args:
        sources: Dict of {source_name: enabled}. Defaults to TrieConfig.sources.

    Returns:
        List of WordEntry, sorted by frequency descending.
    """
    if sources is None:
        sources = TrieConfig().sources

    enabled = {name for name, on in sources.items() if on}

    # Read each source
    raw_counters: dict[str, Counter] = {}
    for name in sorted(enabled):
        if not check_corpus_available(name):
            console.print(f"  [dim][{name}] Not available (not downloaded), skipping[/dim]")
            continue

        console.print(f"  [{name}] Reading...")
        counter = read_corpus(name)
        raw_counters[name] = counter
        console.print(
            f"  [{name}] {len(counter):,} unique words, "
            f"{sum(counter.values()):,} total tokens"
        )

    if not raw_counters:
        console.print("  [red]ERROR: No sources loaded![/red]")
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

    entries.sort(key=lambda e: e.frequency, reverse=True)

    # Decompose compound phrases into base vocabulary
    entries = _decompose_compounds(entries)

    # Print summary
    source_names = sorted(raw_counters.keys())
    console.print(f"\n  Assembled word list:")
    console.print(f"    Total unique words: {len(entries):,}")
    console.print(f"    Sources loaded: {', '.join(source_names)}")

    _print_source_stats(entries, source_names)

    return entries


def _print_source_stats(entries: list[WordEntry], source_names: list[str]) -> None:
    """Print per-source overlap and unique word statistics."""
    total = len(entries)
    if total == 0:
        return

    console.print(f"\n    Per-source statistics:")
    for name in source_names:
        in_source = sum(1 for e in entries if name in e.sources)
        unique = sum(1 for e in entries if e.sources == {name})
        console.print(
            f"      {name:<14} {in_source:>8,} words "
            f"({in_source * 100 / total:5.1f}%), "
            f"{unique:>7,} unique to this source"
        )

    from collections import Counter as C
    source_count_dist = C(len(e.sources) for e in entries)
    console.print(f"\n    Words by source count:")
    for n in sorted(source_count_dist):
        count = source_count_dist[n]
        console.print(f"      In {n} source(s): {count:>8,} ({count * 100 / total:5.1f}%)")


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------


def save_wordlist_csv(entries: list[WordEntry], path: Path) -> None:
    """Save the word list to CSV for inspection."""
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
    console.print(f"  Word list saved to {path} ({len(entries):,} entries)")


def load_wordlist_csv(path: Path) -> list[WordEntry]:
    """Load a previously saved word list from CSV."""
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
