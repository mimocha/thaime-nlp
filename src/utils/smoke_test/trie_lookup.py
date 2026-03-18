"""Trie prefix lookup for smoke testing.

Loads the trie dataset JSON and performs prefix matching on Latin input
to find candidate Thai words at each position. This is a simplified
version of the engine's trie prefix search — operates on the JSON
directly, no compiled trie needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TrieEntry:
    """A word entry from the trie dataset."""

    word_id: int
    thai: str
    frequency: float
    romanizations: list[str]


@dataclass
class TrieData:
    """Loaded trie dataset with lookup structures."""

    entries: list[TrieEntry]
    word_to_id: dict[str, int] = field(default_factory=dict)

    # Prefix index: maps each romanization prefix to list of
    # (romanization, entry) pairs that start with it
    _prefix_index: dict[str, list[tuple[str, TrieEntry]]] = field(
        default_factory=dict, repr=False
    )

    def build_index(self) -> None:
        """Build prefix index for fast lookup."""
        self.word_to_id = {e.thai: e.word_id for e in self.entries}

        # Index every romanization by all its prefixes
        for entry in self.entries:
            for rom in entry.romanizations:
                # Store the full romanization under each prefix length
                for length in range(1, len(rom) + 1):
                    prefix = rom[:length]
                    if prefix not in self._prefix_index:
                        self._prefix_index[prefix] = []
                    self._prefix_index[prefix].append((rom, entry))

    def prefix_match(self, text: str, start: int) -> list[tuple[TrieEntry, str]]:
        """Find all trie entries whose romanization matches text starting at `start`.

        Returns list of (entry, matched_romanization) pairs, deduplicated by
        (word_id, romanization_length). This preserves distinct lattice edges
        when the same word has multiple romanizations of different lengths
        (e.g., "ma" and "maa" both mapping to "มา").
        """
        matches: dict[tuple[int, int], tuple[TrieEntry, str]] = {}
        remaining = text[start:]

        # Try every possible substring length from position `start`
        for length in range(1, len(remaining) + 1):
            substring = remaining[:length]
            if substring not in self._prefix_index:
                # No romanization has this prefix — no longer string will match either.
                break

            # Check if any romanization exactly equals this substring
            for rom, entry in self._prefix_index[substring]:
                if rom == substring:
                    key = (entry.word_id, len(rom))
                    if key not in matches:
                        matches[key] = (entry, rom)

        return list(matches.values())


def load_trie(path: Path) -> TrieData:
    """Load trie dataset from JSON and build prefix index.

    Args:
        path: Path to trie_dataset.json

    Returns:
        TrieData with prefix index built, ready for lookups.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    for raw in data["entries"]:
        entries.append(
            TrieEntry(
                word_id=raw["word_id"],
                thai=raw["thai"],
                frequency=raw["frequency"],
                romanizations=raw["romanizations"],
            )
        )

    trie = TrieData(entries=entries)
    trie.build_index()
    return trie
