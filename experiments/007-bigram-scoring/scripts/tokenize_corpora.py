"""Stage 1: Tokenize Thai corpora and cache token sequences.

Tokenizes each corpus with PyThaiNLP word_tokenize(engine="newmm"),
filters tokens, and writes cached token files (one token per line,
blank line = document boundary).

Usage:
    python -m experiments.007-bigram-scoring.scripts.tokenize_corpora
    python -m experiments.007-bigram-scoring.scripts.tokenize_corpora --corpora wisesight,wongnai
    python -m experiments.007-bigram-scoring.scripts.tokenize_corpora --vocab-filter pipelines/trie/outputs/trie_dataset.json
    python -m experiments.007-bigram-scoring.scripts.tokenize_corpora --workers 4
"""

from __future__ import annotations

import argparse
import bz2
import csv
import json
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from .config import (
    CHUNK_SIZE,
    CORPORA,
    NUM_WORKERS,
    OUTPUT_DIR,
    RAW_DATA_DIR,
    TRIE_DATASET_PATH,
)
from pipelines.trie.wordlist import (
    _clean_wikitext,
    _detect_mediawiki_namespace,
    _is_valid_thai_word,
)

# ---------------------------------------------------------------------------
# Global state for worker processes (set via initializer)
# ---------------------------------------------------------------------------

_vocab: set[str] | None = None


def _init_worker(vocab_set: set[str] | None) -> None:
    """Initialize worker process with shared vocab set."""
    global _vocab
    _vocab = vocab_set


def tokenize_text(text: str) -> list[str]:
    """Tokenize a single text and return filtered tokens.

    Uses the global _vocab set for optional vocabulary filtering.
    """
    from pythainlp.tokenize import word_tokenize

    raw_tokens = word_tokenize(text, engine="newmm")
    tokens = [t for t in raw_tokens if _is_valid_thai_word(t)]

    if _vocab is not None:
        # Vocab filter: replace non-vocab tokens with None (boundary marker)
        filtered = []
        for t in tokens:
            if t in _vocab:
                filtered.append(t)
            else:
                # Insert boundary if last token wasn't already a boundary
                if filtered and filtered[-1] is not None:
                    filtered.append(None)
        return filtered

    return tokens


# ---------------------------------------------------------------------------
# Corpus text iterators
# ---------------------------------------------------------------------------


def iter_wisesight_texts():
    """Yield one text per message from Wisesight sentiment corpus."""
    corpus_dir = RAW_DATA_DIR / "wisesight"
    for fname in ["pos.txt", "neg.txt", "neu.txt", "q.txt"]:
        fpath = corpus_dir / fname
        if not fpath.exists():
            print(f"    WARNING: {fpath} not found, skipping")
            continue
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line


def iter_wongnai_texts():
    """Yield review text from Wongnai restaurant review corpus."""
    wongnai_file = RAW_DATA_DIR / "wongnai" / "w_review_train.csv"
    if not wongnai_file.exists():
        print(f"    WARNING: {wongnai_file} not found, skipping")
        return
    with open(wongnai_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 1 and row[0].strip():
                yield row[0]


def iter_prachathai_texts():
    """Yield title and body_text separately from Prachathai news corpus."""
    prachathai_dir = RAW_DATA_DIR / "prachathai" / "data"
    for fname in ["train.jsonl", "valid.jsonl", "test.jsonl"]:
        fpath = prachathai_dir / fname
        if not fpath.exists():
            print(f"    WARNING: {fpath} not found, skipping")
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


def iter_thwiki_texts():
    """Stream article texts from Thai Wikipedia XML dump."""
    wiki_dir = RAW_DATA_DIR / "thwiki"
    xml_path = wiki_dir / "thwiki-latest-pages-articles.xml"
    bz2_path = wiki_dir / "thwiki-latest-pages-articles.xml.bz2"

    if xml_path.exists():
        open_fn = lambda: open(xml_path, "r", encoding="utf-8")  # noqa: E731
    elif bz2_path.exists():
        open_fn = lambda: bz2.open(bz2_path, "rt", encoding="utf-8")  # noqa: E731
    else:
        print(f"    WARNING: No thwiki dump found in {wiki_dir}")
        return

    # Detect namespace
    with open_fn() as f:
        ns = _detect_mediawiki_namespace(f)

    with open_fn() as f:
        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            if elem.tag == f"{ns}text":
                text = elem.text
                if text:
                    cleaned = _clean_wikitext(text)
                    if cleaned:
                        yield cleaned
                elem.clear()


# ---------------------------------------------------------------------------
# Corpus registry
# ---------------------------------------------------------------------------

_CORPUS_ITERATORS = {
    "wisesight": iter_wisesight_texts,
    "wongnai": iter_wongnai_texts,
    "prachathai": iter_prachathai_texts,
    "thwiki": iter_thwiki_texts,
}


# ---------------------------------------------------------------------------
# Main tokenization logic
# ---------------------------------------------------------------------------


def load_vocab(path: Path) -> set[str]:
    """Load vocabulary from trie dataset JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["thai"] for entry in data["entries"]}


def tokenize_corpus(
    corpus_name: str,
    vocab: set[str] | None,
    num_workers: int,
    output_dir: Path,
) -> Path:
    """Tokenize a single corpus and write token file.

    Returns the output path.
    """
    output_path = output_dir / f"tokens_{corpus_name}.txt"
    iterator_fn = _CORPUS_ITERATORS[corpus_name]

    print(f"\n  [{corpus_name}] Tokenizing...")
    start = time.time()

    # Collect texts into batches for pool.map
    texts = list(iterator_fn())
    total_texts = len(texts)
    print(f"  [{corpus_name}] {total_texts:,} documents to process")

    if total_texts == 0:
        print(f"  [{corpus_name}] No texts found, skipping")
        return output_path

    total_tokens = 0
    total_docs = 0

    with open(output_path, "w", encoding="utf-8") as out:
        if num_workers > 0:
            ctx = get_context("fork")
            with ProcessPoolExecutor(
                max_workers=num_workers,
                mp_context=ctx,
                initializer=_init_worker,
                initargs=(vocab,),
            ) as pool:
                for i, tokens in enumerate(
                    pool.map(tokenize_text, texts, chunksize=CHUNK_SIZE)
                ):
                    if tokens:
                        for t in tokens:
                            if t is None:
                                out.write("\n")  # boundary
                            else:
                                out.write(t + "\n")
                        out.write("\n")  # document boundary
                        total_tokens += sum(1 for t in tokens if t is not None)
                        total_docs += 1

                    if (i + 1) % 10000 == 0:
                        elapsed = time.time() - start
                        print(
                            f"  [{corpus_name}] {i + 1:,}/{total_texts:,} docs, "
                            f"{total_tokens:,} tokens, {elapsed:.0f}s"
                        )
        else:
            # Sequential mode (for debugging)
            _init_worker(vocab)
            for i, text in enumerate(texts):
                tokens = tokenize_text(text)
                if tokens:
                    for t in tokens:
                        if t is None:
                            out.write("\n")
                        else:
                            out.write(t + "\n")
                    out.write("\n")
                    total_tokens += sum(1 for t in tokens if t is not None)
                    total_docs += 1

                if (i + 1) % 10000 == 0:
                    elapsed = time.time() - start
                    print(
                        f"  [{corpus_name}] {i + 1:,}/{total_texts:,} docs, "
                        f"{total_tokens:,} tokens, {elapsed:.0f}s"
                    )

    elapsed = time.time() - start
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"  [{corpus_name}] Done: {total_docs:,} docs, {total_tokens:,} tokens, "
        f"{size_mb:.1f} MB, {elapsed:.1f}s"
    )

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 1: Tokenize Thai corpora and cache token sequences."
    )
    parser.add_argument(
        "--corpora",
        type=str,
        default=",".join(CORPORA),
        help=f"Comma-separated corpus names (default: {','.join(CORPORA)})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=NUM_WORKERS,
        help=f"Number of worker processes (default: {NUM_WORKERS}, 0=sequential)",
    )
    parser.add_argument(
        "--vocab-filter",
        type=str,
        default=None,
        help="Path to trie dataset JSON for vocabulary filtering (recommended)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    corpora = [c.strip() for c in args.corpora.split(",")]
    for c in corpora:
        if c not in _CORPUS_ITERATORS:
            print(f"ERROR: Unknown corpus '{c}'. Available: {', '.join(CORPORA)}")
            sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load vocab filter
    vocab: set[str] | None = None
    if args.vocab_filter:
        vocab_path = Path(args.vocab_filter)
        if not vocab_path.exists():
            print(f"ERROR: Vocab filter file not found: {vocab_path}")
            sys.exit(1)
        print(f"Loading vocabulary from {vocab_path}...")
        vocab = load_vocab(vocab_path)
        print(f"  Vocabulary: {len(vocab):,} words")

    print("=" * 60)
    print("Stage 1: Corpus Tokenization")
    print("=" * 60)
    print(f"  Corpora: {', '.join(corpora)}")
    print(f"  Workers: {args.workers}")
    print(f"  Vocab filter: {'yes' if vocab else 'no'}")
    print(f"  Output: {output_dir}")

    start = time.time()
    for corpus_name in corpora:
        tokenize_corpus(corpus_name, vocab, args.workers, output_dir)

    elapsed = time.time() - start
    print(f"\nAll corpora tokenized in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
