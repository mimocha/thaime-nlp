"""N-gram binary parser and Stupid Backoff scorer for smoke testing.

Reads the thaime ngram binary format (TNLM v1) and provides a scoring
interface for word sequences using Stupid Backoff.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


# Binary format constants (must match pipelines/ngram/encode.py)
MAGIC = b"TNLM"
HEADER_SIZE = 32
SMOOTHING_NAMES = {0: "sbo", 1: "mkn", 2: "katz"}

# Floor probability for unseen n-gram words (matches engine FLOOR_PROB)
FLOOR_PROB = 6e-6


@dataclass
class NgramHeader:
    """Parsed binary header."""

    format_version: int
    flags: int
    vocab_size: int
    smoothing: int
    min_count: int
    n_unigrams: int
    n_bigrams: int
    n_trigrams: int
    alpha: float
    build_info: int


@dataclass
class NgramModel:
    """Loaded n-gram language model from binary file."""

    header: NgramHeader
    string_table: list[str]
    word_to_id: dict[str, int]

    # Scores: word_id -> log10(P(w))
    unigram_scores: list[float] = field(default_factory=list)

    # Scores: (w1_id, w2_id) -> log10(P(w2|w1))
    bigram_scores: dict[tuple[int, int], float] = field(default_factory=dict)

    # Scores: (w1_id, w2_id, w3_id) -> log10(P(w3|w1,w2))
    trigram_scores: dict[tuple[int, int, int], float] = field(default_factory=dict)

    def unigram_prob(self, w: str) -> float:
        """Return linear probability P(w) for a Thai word string.

        Looks up the word in the n-gram model. Returns FLOOR_PROB for unknown words.
        """
        w_id = self.word_to_id.get(w)
        if w_id is not None and 0 <= w_id < len(self.unigram_scores):
            return 10 ** self.unigram_scores[w_id]
        return FLOOR_PROB

    def bigram_score(self, w_prev: str | None, w: str) -> float:
        """Return linear Stupid Backoff probability for P(w|w_prev).

        At BOS (w_prev is None), returns unigram prob without alpha penalty.
        """
        alpha = self.header.alpha
        w_id = self.word_to_id.get(w)

        if w_prev is not None:
            prev_id = self.word_to_id.get(w_prev)
            if prev_id is not None and w_id is not None:
                key = (prev_id, w_id)
                if key in self.bigram_scores:
                    return 10 ** self.bigram_scores[key]
            # Backoff: alpha * unigram
            return alpha * self.unigram_prob(w)
        else:
            # BOS: no alpha penalty
            return self.unigram_prob(w)

    def trigram_score(self, w_prev2: str | None, w_prev1: str | None, w: str) -> float:
        """Return linear Stupid Backoff probability for P(w|w_prev2,w_prev1).

        Handles BOS correctly: no alpha penalty when backing off due to
        missing context (None), only when backing off from a level where
        context was available but no n-gram entry was found.
        """
        alpha = self.header.alpha
        w_id = self.word_to_id.get(w)

        # Try trigram if both previous words available
        if w_prev2 is not None and w_prev1 is not None:
            prev2_id = self.word_to_id.get(w_prev2)
            prev1_id = self.word_to_id.get(w_prev1)
            if prev2_id is not None and prev1_id is not None and w_id is not None:
                key = (prev2_id, prev1_id, w_id)
                if key in self.trigram_scores:
                    return 10 ** self.trigram_scores[key]
            # Had trigram context but no entry found — apply alpha on backoff
            return alpha * self.bigram_score(w_prev1, w)
        else:
            # No trigram context (BOS) — no alpha penalty
            return self.bigram_score(w_prev1, w)


def load_ngram_binary(path: Path) -> NgramModel:
    """Load an n-gram binary file (TNLM format).

    Args:
        path: Path to .bin file (e.g., thaime_ngram_v1_mc15.bin)

    Returns:
        NgramModel ready for scoring.

    Raises:
        ValueError: If magic bytes or format version don't match.
    """
    with open(path, "rb") as f:
        # Parse header
        header_data = f.read(HEADER_SIZE)
        (
            magic, fmt_ver, flags, vocab_size,
            smooth_byte, min_count, n_uni, n_bi, n_tri,
            alpha, build_info,
        ) = struct.unpack("<4sHHHBBIIIfI", header_data)

        if magic != MAGIC:
            raise ValueError(f"Invalid magic bytes: {magic!r} (expected {MAGIC!r})")
        if fmt_ver != 1:
            raise ValueError(f"Unsupported format version: {fmt_ver} (expected 1)")

        header = NgramHeader(
            format_version=fmt_ver,
            flags=flags,
            vocab_size=vocab_size,
            smoothing=smooth_byte,
            min_count=min_count,
            n_unigrams=n_uni,
            n_bigrams=n_bi,
            n_trigrams=n_tri,
            alpha=alpha,
            build_info=build_info,
        )

        # Read string table
        string_table: list[str] = []
        word_to_id: dict[str, int] = {}
        for i in range(vocab_size):
            str_len = struct.unpack("<B", f.read(1))[0]
            word = f.read(str_len).decode("utf-8")
            string_table.append(word)
            word_to_id[word] = i

        # Read unigram scores
        unigram_data = f.read(4 * vocab_size)
        unigram_scores = list(struct.unpack(f"<{vocab_size}f", unigram_data))

        # Read bigram scores
        bigram_scores: dict[tuple[int, int], float] = {}
        for _ in range(n_bi):
            w1_id, w2_id, score = struct.unpack("<HHf", f.read(8))
            bigram_scores[(w1_id, w2_id)] = score

        # Read trigram scores
        trigram_scores: dict[tuple[int, int, int], float] = {}
        for _ in range(n_tri):
            w1_id, w2_id, w3_id, _pad, score = struct.unpack("<HHHHf", f.read(12))
            trigram_scores[(w1_id, w2_id, w3_id)] = score

    model = NgramModel(
        header=header,
        string_table=string_table,
        word_to_id=word_to_id,
        unigram_scores=unigram_scores,
        bigram_scores=bigram_scores,
        trigram_scores=trigram_scores,
    )

    return model
