"""Per-corpus readers for Thai NLP corpora.

Each corpus has a streaming iterator (``iter_<corpus>_texts()``) that
yields raw text strings. The ``CORPUS_REGISTRY`` maps corpus names to
their iterators. Use ``iter_corpus_texts()`` as the primary API.

PyThaiNLP is a dictionary-only source with no text to stream —
use ``read_pythainlp()`` directly.
"""

from __future__ import annotations

import bz2
import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from src.corpora.cleanup import clean_wikitext, detect_mediawiki_namespace


# ---------------------------------------------------------------------------
# Raw data path (resolved once)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RAW_DATA_DIR = _REPO_ROOT / "data" / "corpora" / "raw"


# ---------------------------------------------------------------------------
# Corpus registry
# ---------------------------------------------------------------------------


@dataclass
class CorpusEntry:
    """Registry entry for a corpus."""

    name: str
    iterator: Callable[[], Iterator[str]] | None
    has_text: bool  # False for dictionary-only sources (e.g. pythainlp)


CORPUS_REGISTRY: dict[str, CorpusEntry] = {}


def _register(
    name: str,
    iterator: Callable[[], Iterator[str]] | None = None,
    has_text: bool = True,
) -> None:
    CORPUS_REGISTRY[name] = CorpusEntry(
        name=name, iterator=iterator, has_text=has_text,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def iter_corpus_texts(name: str) -> Iterator[str]:
    """Yield raw text strings from a corpus.

    Raises ``KeyError`` if *name* is not in ``CORPUS_REGISTRY``.
    Raises ``ValueError`` if the corpus has no text iterator (e.g. pythainlp).
    """
    entry = CORPUS_REGISTRY[name]
    if entry.iterator is None:
        raise ValueError(f"Corpus '{name}' has no text iterator (dictionary-only source)")
    return entry.iterator()


def check_corpus_available(name: str) -> bool:
    """Check if a corpus has data available to read."""
    if name == "pythainlp":
        return True  # Always available (built-in)
    corpus_dir = _RAW_DATA_DIR / name
    if name == "thwiki":
        xml_path = corpus_dir / "thwiki-latest-pages-articles.xml"
        bz2_path = corpus_dir / "thwiki-latest-pages-articles.xml.bz2"
        return xml_path.exists() or bz2_path.exists()
    return corpus_dir.exists() and any(corpus_dir.iterdir())


# ---------------------------------------------------------------------------
# Wisesight
# ---------------------------------------------------------------------------


def iter_wisesight_texts() -> Iterator[str]:
    """Yield one text per message from Wisesight sentiment corpus."""
    corpus_dir = _RAW_DATA_DIR / "wisesight"
    for fname in ["pos.txt", "neg.txt", "neu.txt", "q.txt"]:
        fpath = corpus_dir / fname
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line


_register("wisesight", iter_wisesight_texts)


# ---------------------------------------------------------------------------
# Wongnai
# ---------------------------------------------------------------------------


def iter_wongnai_texts() -> Iterator[str]:
    """Yield review text from Wongnai restaurant review corpus."""
    wongnai_file = _RAW_DATA_DIR / "wongnai" / "w_review_train.csv"
    if not wongnai_file.exists():
        return
    with open(wongnai_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 1 and row[0].strip():
                yield row[0]


_register("wongnai", iter_wongnai_texts)


# ---------------------------------------------------------------------------
# Prachathai
# ---------------------------------------------------------------------------


def iter_prachathai_texts() -> Iterator[str]:
    """Yield title and body_text separately from Prachathai news corpus."""
    prachathai_dir = _RAW_DATA_DIR / "prachathai" / "data"
    for fname in ["train.jsonl", "valid.jsonl", "test.jsonl"]:
        fpath = prachathai_dir / fname
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    for field in ("title", "body_text"):
                        text = data.get(field, "")
                        if text:
                            yield text
                except json.JSONDecodeError:
                    continue


_register("prachathai", iter_prachathai_texts)


# ---------------------------------------------------------------------------
# Thai Wikipedia
# ---------------------------------------------------------------------------


def iter_thwiki_texts() -> Iterator[str]:
    """Stream cleaned article texts from Thai Wikipedia XML dump."""
    wiki_dir = _RAW_DATA_DIR / "thwiki"
    xml_path = wiki_dir / "thwiki-latest-pages-articles.xml"
    bz2_path = wiki_dir / "thwiki-latest-pages-articles.xml.bz2"

    if xml_path.exists():
        open_fn = lambda: open(xml_path, "r", encoding="utf-8")  # noqa: E731
    elif bz2_path.exists():
        open_fn = lambda: bz2.open(bz2_path, "rt", encoding="utf-8")  # noqa: E731
    else:
        return

    # Detect namespace
    with open_fn() as f:
        ns = detect_mediawiki_namespace(f)

    with open_fn() as f:
        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            if elem.tag == f"{ns}text":
                text = elem.text
                if text:
                    cleaned = clean_wikitext(text)
                    if cleaned:
                        yield cleaned
                elem.clear()


_register("thwiki", iter_thwiki_texts)


# ---------------------------------------------------------------------------
# PyThaiNLP (dictionary-only, no text to stream)
# ---------------------------------------------------------------------------


def read_pythainlp() -> Counter:
    """Load PyThaiNLP's built-in Thai word list.

    Returns a Counter with uniform count of 1 per word (no frequency data).
    """
    from pythainlp.corpus.common import thai_words

    words = thai_words()
    counter: Counter = Counter()
    for word in words:
        if is_valid_thai_word(word):
            counter[word] = 1

    return counter


# Import at module level for use in read_pythainlp
from src.corpora.validation import is_valid_thai_word  # noqa: E402

_register("pythainlp", iterator=None, has_text=False)
