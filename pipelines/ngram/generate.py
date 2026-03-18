"""N-gram generation pipeline — main entry point.

Tokenizes Thai corpora, counts n-grams (unigrams, bigrams, trigrams),
and validates coverage against the ranking benchmark.

Usage:
    python -m pipelines ngram run
    python -m pipelines ngram run --corpora wisesight,wongnai
    python -m pipelines ngram tokenize --workers 4
    python -m pipelines ngram count
    python -m pipelines ngram validate
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import click

from pipelines.cache import check_cache
from pipelines.config import NgramConfig
from pipelines.console import console
from src.corpora.readers import iter_corpus_texts
from src.corpora.tokenizer import tokenize_with_boundaries

_cfg = NgramConfig()


# ---------------------------------------------------------------------------
# Global state for worker processes (set via initializer)
# ---------------------------------------------------------------------------

_vocab: set[str] | None = None


def _init_worker(vocab_set: set[str] | None) -> None:
    """Initialize worker process with shared vocab set."""
    global _vocab
    _vocab = vocab_set


def _tokenize_text(text: str) -> list[str | None]:
    """Tokenize a single text using the global _vocab set."""
    return tokenize_with_boundaries(text, vocab=_vocab)


# ---------------------------------------------------------------------------
# Tokenization
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
    tokens_dir: Path,
) -> Path:
    """Tokenize a single corpus and write token file.

    Returns the output path.
    """
    output_path = tokens_dir / f"tokens_{corpus_name}.txt"

    console.print(f"\n  [{corpus_name}] Tokenizing...")
    start = time.time()

    texts = list(iter_corpus_texts(corpus_name))
    total_texts = len(texts)
    console.print(f"  [{corpus_name}] {total_texts:,} documents to process")

    if total_texts == 0:
        console.print(f"  [{corpus_name}] No texts found, skipping")
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
                    pool.map(_tokenize_text, texts, chunksize=_cfg.chunk_size)
                ):
                    while tokens and tokens[-1] is None:
                        tokens.pop()
                    if tokens:
                        for t in tokens:
                            if t is None:
                                out.write("\n")
                            else:
                                out.write(t + "\n")
                        out.write("\n")
                        total_tokens += sum(1 for t in tokens if t is not None)
                        total_docs += 1

                    if (i + 1) % _cfg.log_interval == 0:
                        elapsed = time.time() - start
                        console.print(
                            f"  [{corpus_name}] {i + 1:,}/{total_texts:,} docs, "
                            f"{total_tokens:,} tokens, {elapsed:.0f}s"
                        )
        else:
            _init_worker(vocab)
            for i, text in enumerate(texts):
                tokens = _tokenize_text(text)
                while tokens and tokens[-1] is None:
                    tokens.pop()
                if tokens:
                    for t in tokens:
                        if t is None:
                            out.write("\n")
                        else:
                            out.write(t + "\n")
                    out.write("\n")
                    total_tokens += sum(1 for t in tokens if t is not None)
                    total_docs += 1

                if (i + 1) % _cfg.log_interval == 0:
                    elapsed = time.time() - start
                    console.print(
                        f"  [{corpus_name}] {i + 1:,}/{total_texts:,} docs, "
                        f"{total_tokens:,} tokens, {elapsed:.0f}s"
                    )

    elapsed = time.time() - start
    size_mb = output_path.stat().st_size / (1024 * 1024)
    console.print(
        f"  [{corpus_name}] Done: {total_docs:,} docs, {total_tokens:,} tokens, "
        f"{size_mb:.1f} MB, {elapsed:.1f}s"
    )

    return output_path


# ---------------------------------------------------------------------------
# Shared option decorators
# ---------------------------------------------------------------------------


def _common_options(f):
    """Options shared across subcommands."""
    f = click.option(
        "--corpora", default=",".join(_cfg.corpora),
        help=f"Comma-separated corpus names (default: {','.join(_cfg.corpora)})",
    )(f)
    f = click.option(
        "--output-dir", default=None, type=click.Path(),
        help="Base output directory",
    )(f)
    return f


def _resolve_common(corpora: str, output_dir: str | None) -> tuple[list[str], Path]:
    """Parse common options into usable values."""
    corpora_list = [c.strip() for c in corpora.split(",")]
    out = Path(output_dir) if output_dir else _cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)
    return corpora_list, out


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """N-gram generation pipeline for THAIME."""


# ---------------------------------------------------------------------------
# run — full pipeline
# ---------------------------------------------------------------------------


@cli.command()
@_common_options
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers}, 0=sequential)")
@click.option("--vocab-filter", default=None, type=click.Path(), help="Path to trie dataset JSON for vocabulary filtering")
@click.option("--no-vocab-filter", is_flag=True, help="Disable vocabulary filtering")
@click.option("--min-count", default=2, type=int, help="Minimum n-gram count in output (default: 2)")
@click.option("--no-cache", is_flag=True, help="Force re-tokenization even if token files exist")
@click.option("--encode-min-count", default=_cfg.encode_min_count, type=int, help=f"Minimum raw n-gram count for encode (default: {_cfg.encode_min_count})")
@click.option("--alpha", default=_cfg.encode_alpha, type=float, help=f"Stupid Backoff alpha (default: {_cfg.encode_alpha})")
@click.option("--smoothing", default=_cfg.encode_smoothing, type=click.Choice(["sbo", "mkn", "katz"]), help=f"Smoothing method (default: {_cfg.encode_smoothing})")
@click.pass_context
def run(ctx, corpora, output_dir, workers, vocab_filter, no_vocab_filter, min_count, no_cache, encode_min_count, alpha, smoothing):
    """Run the full pipeline: tokenize, count, validate, encode."""
    # Inherit global options
    parent = ctx.parent.obj if ctx.parent and ctx.parent.obj else {}
    if parent.get("no_cache"):
        no_cache = True
    if parent.get("workers") is not None:
        workers = parent["workers"]

    corpora_list, base = _resolve_common(corpora, output_dir)
    tokens_dir = base / "tokens"
    ngram_dir = base / "ngram"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    ngram_dir.mkdir(parents=True, exist_ok=True)

    # Resolve vocab filter path
    if vocab_filter is None and not no_vocab_filter:
        default_trie = _cfg.trie_dataset_path
        if default_trie.exists():
            vocab_filter = str(default_trie)

    pipeline_start = time.time()

    console.print("=" * 60)
    console.print("N-gram Generation Pipeline")
    console.print("=" * 60)
    console.print(f"  Corpora: {', '.join(corpora_list)}")
    console.print(f"  Workers: {workers}")
    console.print(f"  Vocab filter: {'no' if no_vocab_filter else (vocab_filter or 'not found')}")
    console.print(f"  Output: {base}")

    if not no_vocab_filter and vocab_filter:
        vocab_path = Path(vocab_filter)
        if not vocab_path.exists():
            console.print(f"[red]ERROR: Vocab filter file not found: {vocab_path}[/red]")
            sys.exit(1)

    # Stage 1: Tokenize
    _run_tokenize_stage(corpora_list, tokens_dir, workers, vocab_filter, no_vocab_filter, no_cache)

    # Stage 2: Count
    _run_count_stage(corpora_list, tokens_dir, ngram_dir, min_count)

    # Stage 3: Validate
    _run_validate_stage(ngram_dir)

    # Stage 4: Encode
    trie_path = _cfg.trie_dataset_path
    if vocab_filter:
        trie_path = Path(vocab_filter)
    _run_encode_stage(ngram_dir, trie_path, ngram_dir, encode_min_count, alpha, smoothing)

    # Summary
    total_elapsed = time.time() - pipeline_start
    console.print(f"\n{'=' * 60}")
    console.print("Pipeline complete!")
    console.print(f"{'=' * 60}")
    _print_output_summary(base)
    console.print(f"  Total time: {total_elapsed:.1f}s")


# ---------------------------------------------------------------------------
# tokenize — Stage 1 only
# ---------------------------------------------------------------------------


@cli.command()
@_common_options
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers}, 0=sequential)")
@click.option("--vocab-filter", default=None, type=click.Path(), help="Path to trie dataset JSON for vocabulary filtering")
@click.option("--no-vocab-filter", is_flag=True, help="Disable vocabulary filtering")
def tokenize(corpora, output_dir, workers, vocab_filter, no_vocab_filter):
    """Stage 1: Tokenize corpora into cached token files."""
    corpora_list, base = _resolve_common(corpora, output_dir)
    tokens_dir = base / "tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    _run_tokenize_stage(corpora_list, tokens_dir, workers, vocab_filter, no_vocab_filter, no_cache=True)
    _print_output_summary(base)


# ---------------------------------------------------------------------------
# count — Stage 2 only
# ---------------------------------------------------------------------------


@cli.command()
@_common_options
@click.option("--min-count", default=2, type=int, help="Minimum n-gram count in output (default: 2)")
def count(corpora, output_dir, min_count):
    """Stage 2: Count n-grams from cached token files."""
    corpora_list, base = _resolve_common(corpora, output_dir)
    tokens_dir = base / "tokens"
    ngram_dir = base / "ngram"
    ngram_dir.mkdir(parents=True, exist_ok=True)
    _run_count_stage(corpora_list, tokens_dir, ngram_dir, min_count)
    _print_output_summary(base)


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------


def _run_tokenize_stage(
    corpora_list: list[str],
    tokens_dir: Path,
    workers: int,
    vocab_filter: str | None,
    no_vocab_filter: bool,
    no_cache: bool,
) -> None:
    """Run Stage 1: corpus tokenization."""
    console.print(f"\n{'=' * 60}")
    console.print("Stage 1: Corpus Tokenization")
    console.print(f"{'=' * 60}")

    # Check cache
    all_cached = not no_cache and all(
        check_cache(tokens_dir / f"tokens_{c}.txt") for c in corpora_list
    )

    if all_cached:
        console.print("  All token files cached, skipping tokenization.")
        console.print("  Use --no-cache to force re-tokenization.")
        return

    # Load vocab
    tok_vocab: set[str] | None = None
    if not no_vocab_filter and vocab_filter:
        vocab_path = Path(vocab_filter)
        if not vocab_path.exists():
            console.print(f"[red]ERROR: Vocab filter file not found: {vocab_path}[/red]")
            sys.exit(1)
        console.print(f"  Loading vocabulary from {vocab_path}...")
        tok_vocab = load_vocab(vocab_path)
        console.print(f"  Vocabulary: {len(tok_vocab):,} words")

    start = time.time()
    for corpus_name in corpora_list:
        tokenize_corpus(corpus_name, tok_vocab, workers, tokens_dir)
    elapsed = time.time() - start
    console.print(f"\n  Tokenization complete in {elapsed:.1f}s")


def _run_count_stage(
    corpora_list: list[str],
    tokens_dir: Path,
    ngram_dir: Path,
    min_count: int,
) -> None:
    """Run Stage 2: n-gram counting for n=1, 2, 3."""
    console.print(f"\n{'=' * 60}")
    console.print("Stage 2: N-gram Counting")
    console.print(f"{'=' * 60}")

    # Verify token files exist
    for corpus_name in corpora_list:
        token_path = tokens_dir / f"tokens_{corpus_name}.txt"
        if not token_path.exists():
            console.print(f"[red]ERROR: Token file not found: {token_path}[/red]")
            console.print("  Run 'tokenize' first.")
            sys.exit(1)

    from pipelines.ngram.count import (
        count_worker,
        normalize_and_merge,
        save_ngrams_freq_tsv,
        save_ngrams_tsv,
    )

    start = time.time()
    for n in (1, 2, 3):
        console.print(f"\n  --- {n}-grams ---")

        token_paths = [tokens_dir / f"tokens_{c}.txt" for c in corpora_list]
        corpus_counters: dict[str, Counter] = {}
        for tp in token_paths:
            corpus_name, counter = count_worker((tp, n, None))
            corpus_counters[corpus_name] = counter
            console.print(
                f"    [{corpus_name}] {len(counter):,} unique, "
                f"{sum(counter.values()):,} total"
            )

        # Per-corpus TSVs
        for corpus_name, counter in corpus_counters.items():
            out_path = ngram_dir / f"ngrams_{n}_{corpus_name}.tsv"
            written = save_ngrams_tsv(counter, out_path, min_count)
            size_mb = out_path.stat().st_size / (1024 * 1024)
            console.print(f"    {out_path.name}: {written:,} ({size_mb:.1f} MB)")

        # Raw merge
        raw_merged: Counter = Counter()
        for counter in corpus_counters.values():
            raw_merged.update(counter)
        raw_path = ngram_dir / f"ngrams_{n}_merged_raw.tsv"
        raw_written = save_ngrams_tsv(raw_merged, raw_path, min_count)
        size_mb = raw_path.stat().st_size / (1024 * 1024)
        console.print(f"    {raw_path.name}: {raw_written:,} ({size_mb:.1f} MB)")

        # Normalized merge
        norm_merged = normalize_and_merge(corpus_counters)
        norm_path = ngram_dir / f"ngrams_{n}_merged.tsv"
        norm_written = save_ngrams_freq_tsv(norm_merged, norm_path)
        size_mb = norm_path.stat().st_size / (1024 * 1024)
        console.print(f"    {norm_path.name}: {norm_written:,} ({size_mb:.1f} MB)")

    elapsed = time.time() - start
    console.print(f"\n  Counting complete in {elapsed:.1f}s")


def _run_validate_stage(ngram_dir: Path) -> None:
    """Run Stage 3: validation."""
    console.print(f"\n{'=' * 60}")
    console.print("Stage 3: Validation")
    console.print(f"{'=' * 60}")

    from pipelines.ngram.validate import run_validation
    run_validation(ngram_dir)


def _run_encode_stage(
    ngram_dir: Path,
    trie_path: Path,
    output_dir: Path,
    min_count: int,
    alpha: float,
    smoothing: str,
) -> None:
    """Run Stage 4: binary encoding."""
    if not trie_path.exists():
        console.print(f"\n  [yellow]WARNING: Trie dataset not found at {trie_path}[/yellow]")
        console.print(f"  Skipping encode stage. Run 'python -m pipelines trie run' first.")
        return

    console.print(f"\n{'=' * 60}")
    console.print("Stage 4: Binary Encoding")
    console.print(f"{'=' * 60}")
    console.print(f"  min_count={min_count}, smoothing={smoothing}, α={alpha}")

    from pipelines.ngram.encode import run_encode
    from pipelines.config import TEXT_CORPORA

    result = run_encode(
        ngram_dir=ngram_dir,
        trie_path=trie_path,
        output_dir=output_dir,
        corpora=list(TEXT_CORPORA),
        min_count=min_count,
        alpha=alpha,
        smoothing=smoothing,
    )
    if not result:
        console.print(f"  [red]Encode stage failed[/red]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_output_summary(base: Path) -> None:
    """Print a summary of output files and their sizes."""
    console.print(f"\n  Output directory: {base}")
    for subdir in ["tokens", "ngram"]:
        d = base / subdir
        if d.exists():
            console.print(f"  {subdir}/:")
            for path in sorted(d.glob("*")):
                if path.is_file():
                    size_mb = path.stat().st_size / (1024 * 1024)
                    console.print(f"    {path.name}: {size_mb:.1f} MB")


# ---------------------------------------------------------------------------
# Register validate subcommand
# ---------------------------------------------------------------------------


from pipelines.ngram.validate import validate as _validate_cmd  # noqa: E402
from pipelines.ngram.encode import encode as _encode_cmd  # noqa: E402

cli.add_command(_validate_cmd, "validate")
cli.add_command(_encode_cmd, "encode")


if __name__ == "__main__":
    cli()
