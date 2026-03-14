"""Shared corpus reading, tokenization, and validation utilities.

This package centralizes corpus access for all pipelines:
- validation: Thai word filtering heuristics
- cleanup: Wikitext markup removal
- tokenizer: PyThaiNLP tokenization with filtering
- readers: Per-corpus readers (Counter-returning + streaming iterators)
"""

from src.corpora.validation import is_valid_thai_word
from src.corpora.tokenizer import tokenize_and_filter, tokenize_with_boundaries
from src.corpora.readers import CORPUS_REGISTRY, iter_corpus_texts, read_corpus

__all__ = [
    "is_valid_thai_word",
    "tokenize_and_filter",
    "tokenize_with_boundaries",
    "CORPUS_REGISTRY",
    "iter_corpus_texts",
    "read_corpus",
]
