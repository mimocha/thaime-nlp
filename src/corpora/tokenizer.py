"""Thai text tokenization with filtering.

Provides two tokenization modes:
- ``tokenize_and_filter()``: returns only valid Thai words (for word counting)
- ``tokenize_with_boundaries()``: returns tokens with boundary markers (for n-gram adjacency)

Both use PyThaiNLP ``word_tokenize(engine="newmm")``.
"""

from __future__ import annotations

from collections import Counter

from pythainlp.tokenize import word_tokenize

from src.corpora.validation import is_valid_thai_word


def tokenize_and_filter(text: str) -> list[str]:
    """Tokenize Thai text and return only valid Thai words.

    Used by the trie pipeline for word frequency counting.
    """
    tokens = word_tokenize(text, engine="newmm")
    return [t for t in tokens if is_valid_thai_word(t)]


def tokenize_chunk(texts: list[str]) -> Counter:
    """Tokenize a batch of texts and return combined word counts.

    Worker function for parallel wordlist assembly. Each text is tokenized
    independently — no cross-text batching.
    """
    counter: Counter = Counter()
    for text in texts:
        counter.update(tokenize_and_filter(text))
    return counter


def tokenize_with_boundaries(
    text: str,
    vocab: set[str] | None = None,
) -> list[str | None]:
    """Tokenize text, replacing non-Thai tokens with boundary markers.

    Non-Thai tokens become ``None`` (sequence boundary) to prevent false
    n-gram adjacencies. If *vocab* is provided, non-vocab Thai tokens
    are also replaced with boundaries.

    Used by the n-gram pipeline for token sequence generation.
    """
    raw_tokens = word_tokenize(text, engine="newmm")

    # Filter non-Thai tokens, inserting boundaries where they were dropped
    filtered: list[str | None] = []
    for t in raw_tokens:
        if is_valid_thai_word(t):
            filtered.append(t)
        elif filtered and filtered[-1] is not None:
            filtered.append(None)  # boundary marker

    if vocab is not None:
        # Vocab filter: replace non-vocab tokens with boundary markers
        vocab_filtered: list[str | None] = []
        for t in filtered:
            if t is None:
                # Preserve existing boundaries
                if vocab_filtered and vocab_filtered[-1] is not None:
                    vocab_filtered.append(None)
            elif t in vocab:
                vocab_filtered.append(t)
            elif vocab_filtered and vocab_filtered[-1] is not None:
                vocab_filtered.append(None)
        return vocab_filtered

    return filtered
