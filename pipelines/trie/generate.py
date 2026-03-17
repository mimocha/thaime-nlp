"""Trie generation pipeline — main entry point.

Assembles a Thai word list from multiple sources, generates romanization
variants for each word using the dictionary-driven variant generator,
and exports a trie-ready dataset.

Usage:
    python -m pipelines trie run
    python -m pipelines trie run --sources wisesight,wongnai,pythainlp
    python -m pipelines trie run --workers 8 --no-cache
    python -m pipelines trie wordlist --sources wisesight,wongnai
    python -m pipelines trie variant --workers 4
    python -m pipelines trie export
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
import time
import tomllib
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path

import click
import yaml

from pipelines.cache import check_cache
from pipelines.config import TrieConfig
from pipelines.console import console
from pipelines.trie.wordlist import (
    WordEntry,
    assemble_wordlist,
    load_wordlist_csv,
    save_wordlist_csv,
)

logger = logging.getLogger(__name__)

# Default config instance
_cfg = TrieConfig()
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"


def _load_project_version() -> str:
    """Load the package version from pyproject.toml."""
    try:
        with open(_PYPROJECT_PATH, "rb") as f:
            pyproject = tomllib.load(f)
        version = pyproject.get("project", {}).get("version")
        if isinstance(version, str) and version:
            return version
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.error("Failed to load project version from %s: %s", _PYPROJECT_PATH, e)

    return "unknown_version"


_PROJECT_VERSION = _load_project_version()


# ---------------------------------------------------------------------------
# Variant generation (single word — used by worker processes)
# ---------------------------------------------------------------------------


def _generate_variants_for_word(args: tuple[str, int]) -> tuple[str, int, list[str]]:
    """Generate variants for a single word. Used as multiprocessing target."""
    thai_word, max_variants = args
    try:
        from src.variant_generator import generate_word_variants
        variants = generate_word_variants(thai_word, max_variants=max_variants)
    except Exception as e:
        logger.error("Failed to generate variants for %s: %s", thai_word, e)
        variants = []
    return (thai_word, -1, variants)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _save_variants_checkpoint(results: dict[str, list[str]], path: Path) -> None:
    """Save intermediate variant results to a JSON checkpoint file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)


def _load_variants_checkpoint(path: Path) -> dict[str, list[str]]:
    """Load variant results from a checkpoint file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Manual overrides
# ---------------------------------------------------------------------------


def load_overrides(path: Path | None = None) -> dict[str, list[str]]:
    """Load manual romanization overrides from YAML."""
    if path is None:
        try:
            path = _cfg.get_overrides_path()
        except FileNotFoundError:
            return {}
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or not isinstance(raw, dict):
        return {}

    overrides: dict[str, list[str]] = {}
    for word, romanizations in raw.items():
        if isinstance(romanizations, list) and romanizations:
            overrides[str(word)] = [str(r) for r in romanizations]

    return overrides


def apply_overrides(
    entries: list[WordEntry],
    variants: dict[str, list[str]],
    overrides: dict[str, list[str]],
) -> tuple[list[WordEntry], dict[str, list[str]]]:
    """Merge manual overrides into the word list and variants."""
    if not overrides:
        return entries, variants

    existing_words = {e.word for e in entries}
    added = 0

    # Floor frequency for override-only words: use the minimum observed corpus
    # frequency so they rank at the bottom but remain selectable by the Viterbi
    # scorer when bigram/trigram context favors them.
    min_freq = min((e.frequency for e in entries if e.frequency > 0), default=1e-9)

    for word, romanizations in overrides.items():
        variants[word] = romanizations
        if word not in existing_words:
            entries.append(WordEntry(
                word=word, frequency=min_freq, sources={"overrides"},
            ))
            existing_words.add(word)
            added += 1

    replaced = len(overrides) - added
    console.print(f"  Manual overrides applied: {len(overrides)} words "
                   f"({replaced} replaced, {added} new, floor freq={min_freq:.2e})")

    return entries, variants


# ---------------------------------------------------------------------------
# Word exclusion list
# ---------------------------------------------------------------------------


def load_exclusion_list(path: Path | None) -> set[str]:
    """Load a word exclusion list from a plain-text file."""
    if path is None:
        return set()
    if not path.exists():
        console.print(f"  [yellow]WARNING: Exclusion list not found at {path}[/yellow]")
        return set()

    words: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line)
    return words


def apply_exclusion_list(
    entries: list[WordEntry],
    exclusion_words: set[str],
    override_words: set[str],
) -> list[WordEntry]:
    """Remove words on the exclusion list from entries. Override words are exempt."""
    if not exclusion_words:
        return entries

    before = len(entries)
    filtered = [
        e for e in entries
        if e.word not in exclusion_words or e.word in override_words
    ]
    removed = before - len(filtered)

    console.print(f"  Word exclusion list: {removed:,} words removed "
                   f"({len(exclusion_words):,} in list, overrides exempt)")

    return filtered


# ---------------------------------------------------------------------------
# Dataset filters
# ---------------------------------------------------------------------------


_THAI_BASE_CHARS = re.compile(r"[\u0E01-\u0E39\u0E40-\u0E44\u0E47\u0E33]")


def _thai_base_len(word: str) -> int:
    """Count Thai characters excluding tone marks and thanthakhat."""
    return len(_THAI_BASE_CHARS.findall(word))


def filter_dataset(
    entries: list[WordEntry],
    variants: dict[str, list[str]],
    overrides: dict[str, list[str]],
    min_source_count: int = _cfg.min_source_count,
    min_frequency: float = _cfg.min_frequency,
    max_length_ratio: float = _cfg.max_length_ratio,
    vocab_limit: int = _cfg.vocab_limit,
) -> tuple[list[WordEntry], dict[str, list[str]]]:
    """Apply quality filters to the word list after variant generation."""
    override_words = set(overrides.keys())
    before = len(entries)

    filtered: list[WordEntry] = []
    removed_source = 0
    removed_freq = 0
    removed_ratio = 0
    removed_empty = 0

    for entry in entries:
        word = entry.word
        is_override = word in override_words

        # Filter 1: source count (pythainlp-only and overrides exempt)
        if not is_override:
            is_pythainlp_only = entry.sources == {"pythainlp"}
            if not is_pythainlp_only and len(entry.sources) < min_source_count:
                removed_source += 1
                continue

        # Filter 2: frequency (overrides exempt)
        if not is_override and entry.frequency < min_frequency:
            removed_freq += 1
            continue

        # Filter 3: romanization length ratio (overrides exempt)
        if not is_override:
            word_variants = variants.get(word, [])
            if word_variants:
                min_rom_len = min(len(r) for r in word_variants)
                if min_rom_len > 0:
                    base_len = _thai_base_len(word)
                    ratio = base_len / min_rom_len
                    if ratio > max_length_ratio:
                        removed_ratio += 1
                        continue

        # Filter 4: remove words with zero romanization variants
        if not variants.get(word, []):
            removed_empty += 1
            continue

        filtered.append(entry)

    after_filters = len(filtered)

    # Filter 5: vocabulary limit
    removed_vocab_limit = 0
    if vocab_limit > 0 and len(filtered) > vocab_limit:
        override_entries = [e for e in filtered if e.word in override_words]
        regular_entries = [e for e in filtered if e.word not in override_words]
        regular_entries.sort(key=lambda e: e.frequency, reverse=True)
        regular_limit = max(0, vocab_limit - len(override_entries))
        removed_vocab_limit = max(0, len(regular_entries) - regular_limit)
        regular_entries = regular_entries[:regular_limit]
        filtered = override_entries + regular_entries
        filtered.sort(key=lambda e: e.frequency, reverse=True)

    # Clean up variants dict
    kept_words = {e.word for e in filtered}
    filtered_variants = {w: v for w, v in variants.items() if w in kept_words}

    console.print(f"\n  Dataset filtering:")
    console.print(f"    Before:                {before:>8,} words")
    console.print(f"    Removed (source < {min_source_count}):  {removed_source:>8,}")
    console.print(f"    Removed (freq < {min_frequency:.0e}): {removed_freq:>8,}")
    console.print(f"    Removed (ratio > {max_length_ratio}):  {removed_ratio:>8,}")
    console.print(f"    Removed (0 variants):  {removed_empty:>8,}")
    console.print(f"    After quality filters: {after_filters:>8,} words")
    if vocab_limit > 0:
        console.print(f"    Vocab limit:           {vocab_limit:>8,}")
        console.print(f"    Removed (vocab limit): {removed_vocab_limit:>8,}")
    console.print(f"    Final vocabulary:      {len(filtered):>8,} words")

    return filtered, filtered_variants


# Size of each chunk for chunked multiprocessing.
_CHUNK_SIZE = 5000


def run_variant_generation(
    entries: list[WordEntry],
    max_variants: int = _cfg.max_variants_per_word,
    num_workers: int = _cfg.num_workers,
    checkpoint_path: Path | None = None,
) -> dict[str, list[str]]:
    """Generate romanization variants for all words in the word list."""
    words = [e.word for e in entries]
    total = len(words)

    # Load checkpoint if available
    results: dict[str, list[str]] = {}
    if checkpoint_path and checkpoint_path.exists():
        results = _load_variants_checkpoint(checkpoint_path)
        console.print(f"  Loaded checkpoint: {len(results):,} words already processed")

    remaining = [w for w in words if w not in results]
    if not remaining:
        console.print(f"  All {total:,} words already processed (from checkpoint)")
        _print_variant_stats(results, total)
        return results

    console.print(f"\n  Generating variants for {len(remaining):,} remaining words "
                   f"(of {total:,} total, max_variants={max_variants}, workers={num_workers})...")

    start = time.time()
    processed_before = len(results)
    failures = sum(1 for v in results.values() if not v)

    if num_workers > 0:
        for chunk_start in range(0, len(remaining), _CHUNK_SIZE):
            chunk = remaining[chunk_start:chunk_start + _CHUNK_SIZE]
            work_items = [(w, max_variants) for w in chunk]

            ctx = get_context("fork")
            try:
                with ProcessPoolExecutor(
                    max_workers=num_workers, mp_context=ctx,
                ) as pool:
                    for word, _, variants in pool.map(
                        _generate_variants_for_word, work_items, chunksize=50,
                    ):
                        results[word] = variants
                        if not variants:
                            failures += 1
            except Exception as e:
                console.print(f"\n  [yellow]WARNING: Pool crashed on chunk starting at "
                               f"word {chunk_start + processed_before:,}: {e}[/yellow]")
                if checkpoint_path:
                    _save_variants_checkpoint(results, checkpoint_path)
                    console.print(f"  Checkpoint saved with {len(results):,} words processed")
                raise

            done = len(results) - processed_before
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            console.print(
                f"    [{done + processed_before:,}/{total:,}] "
                f"{rate:.0f} words/sec, {failures} failures"
            )

            if checkpoint_path:
                _save_variants_checkpoint(results, checkpoint_path)
    else:
        # Sequential (for debugging)
        from src.variant_generator import generate_word_variants

        for i, word in enumerate(remaining):
            try:
                variants = generate_word_variants(word, max_variants=max_variants)
            except Exception as e:
                logger.warning("Failed: %s: %s", word, e)
                variants = []
            results[word] = variants
            if not variants:
                failures += 1
            if (i + 1) % _cfg.log_interval == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed
                console.print(
                    f"    [{i + 1 + processed_before:,}/{total:,}] "
                    f"{rate:.0f} words/sec, {failures} failures"
                )
                if checkpoint_path:
                    _save_variants_checkpoint(results, checkpoint_path)

    elapsed = time.time() - start
    console.print(f"  Variant generation complete in {elapsed:.1f}s")
    _print_variant_stats(results, total)

    if checkpoint_path and checkpoint_path.exists():
        checkpoint_path.unlink()
        console.print(f"  Checkpoint cleaned up")

    return results


def _print_variant_stats(results: dict[str, list[str]], total: int) -> None:
    """Print summary statistics for variant generation results."""
    failures = sum(1 for v in results.values() if not v)
    console.print(f"    Words processed: {len(results):,}")
    console.print(f"    Failures (0 variants): {failures:,} "
                   f"({failures * 100 / total:.1f}%)")

    variant_counts = [len(v) for v in results.values() if v]
    if variant_counts:
        avg = sum(variant_counts) / len(variant_counts)
        variant_counts_sorted = sorted(variant_counts)
        median = variant_counts_sorted[len(variant_counts_sorted) // 2]
        console.print(f"    Avg variants/word: {avg:.1f}")
        console.print(f"    Median variants/word: {median}")
        console.print(f"    Max variants/word: {max(variant_counts)}")


def build_trie_dataset(
    entries: list[WordEntry],
    variants: dict[str, list[str]],
) -> list[dict]:
    """Build the trie dataset entries with word IDs."""
    dataset = []
    for word_id, entry in enumerate(entries):
        word_variants = variants.get(entry.word, [])
        dataset.append({
            "word_id": word_id,
            "thai": entry.word,
            "frequency": entry.frequency,
            "sources": sorted(entry.sources),
            "romanizations": word_variants,
        })
    return dataset


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_json(
    dataset: list[dict],
    sources_used: list[str],
    path: Path,
) -> None:
    """Export trie dataset as JSON."""
    total_keys = sum(len(e["romanizations"]) for e in dataset)
    all_keys: set[str] = set()
    for e in dataset:
        all_keys.update(e["romanizations"])

    output = {
        "metadata": {
            "version": _PROJECT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vocab_size": len(dataset),
            "total_romanization_keys": total_keys,
            "unique_romanization_keys": len(all_keys),
            "sources": sources_used,
        },
        "entries": dataset,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    size_mb = path.stat().st_size / (1024 * 1024)
    console.print(f"  JSON exported to {path} ({size_mb:.1f} MB)")


def export_csv(dataset: list[dict], path: Path) -> None:
    """Export trie dataset as flat CSV (one row per romanization key)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "word_id", "thai", "romanization_key", "frequency", "sources",
        ])
        for entry in dataset:
            sources_str = "|".join(entry["sources"])
            for roman_key in entry["romanizations"]:
                writer.writerow([
                    entry["word_id"],
                    entry["thai"],
                    roman_key,
                    f"{entry['frequency']:.12f}",
                    sources_str,
                ])
                row_count += 1

    size_mb = path.stat().st_size / (1024 * 1024)
    console.print(f"  CSV exported to {path} ({row_count:,} rows, {size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Statistics report
# ---------------------------------------------------------------------------


def print_stats(dataset: list[dict]) -> None:
    """Print summary statistics for the trie dataset."""
    total_words = len(dataset)
    variant_counts = [len(e["romanizations"]) for e in dataset]
    total_keys = sum(variant_counts)

    all_keys: set[str] = set()
    for e in dataset:
        all_keys.update(e["romanizations"])

    console.print(f"\n{'=' * 60}")
    console.print("Trie Dataset Statistics")
    console.print(f"{'=' * 60}")
    console.print(f"  Vocabulary size:          {total_words:>10,}")
    console.print(f"  Total romanization keys:  {total_keys:>10,}")
    console.print(f"  Unique romanization keys: {len(all_keys):>10,}")

    if variant_counts:
        avg = total_keys / total_words
        sorted_vc = sorted(variant_counts)
        median = sorted_vc[len(sorted_vc) // 2]
        console.print(f"\n  Variants per word:")
        console.print(f"    Average: {avg:.1f}")
        console.print(f"    Median:  {median}")
        console.print(f"    Min:     {min(variant_counts)}")
        console.print(f"    Max:     {max(variant_counts)}")

    # Distribution buckets
    buckets = {"0": 0, "1": 0, "2-5": 0, "6-20": 0, "21-50": 0, "51+": 0}
    for vc in variant_counts:
        if vc == 0:
            buckets["0"] += 1
        elif vc == 1:
            buckets["1"] += 1
        elif vc <= 5:
            buckets["2-5"] += 1
        elif vc <= 20:
            buckets["6-20"] += 1
        elif vc <= 50:
            buckets["21-50"] += 1
        else:
            buckets["51+"] += 1

    console.print(f"\n  Variant count distribution:")
    for label, count in buckets.items():
        pct = count * 100 / total_words if total_words else 0
        console.print(f"    {label:>5} variants: {count:>8,} words ({pct:5.1f}%)")

    # Collision report
    key_to_words: dict[str, list[str]] = {}
    for e in dataset:
        for key in e["romanizations"]:
            key_to_words.setdefault(key, []).append(e["thai"])

    collisions = {k: v for k, v in key_to_words.items() if len(v) > 1}
    if collisions:
        console.print(f"\n  Romanization key collisions:")
        console.print(f"    Keys mapping to 2+ Thai words: {len(collisions):,}")
        top_collisions = sorted(
            collisions.items(), key=lambda x: len(x[1]), reverse=True
        )[:10]
        for key, words in top_collisions:
            console.print(f"    '{key}' -> {len(words)} words: {', '.join(words[:5])}")
            if len(words) > 5:
                console.print(f"      ... and {len(words) - 5} more")


# ---------------------------------------------------------------------------
# Shared option helpers
# ---------------------------------------------------------------------------


def _parse_sources(sources_str: str | None) -> dict[str, bool]:
    """Parse --sources option into sources dict."""
    sources = dict(_cfg.sources)
    if sources_str:
        sources = {name: False for name in sources}
        for name in sources_str.split(","):
            name = name.strip()
            if name in sources:
                sources[name] = True
            else:
                console.print(f"[red]ERROR: Unknown source '{name}'[/red]")
                sys.exit(1)
    return sources


def _resolve_output_dir(output_dir: str | None, subdir: str) -> Path:
    """Resolve and create output directory."""
    base = Path(output_dir) if output_dir else _cfg.output_dir
    out = base / subdir
    out.mkdir(parents=True, exist_ok=True)
    return out


def _setup_variant_logging(output_dir: Path) -> None:
    """Set up variant strategy log file."""
    log_path = output_dir / "variant_strategies.log"
    variant_logger = logging.getLogger("src.variant_generator")
    variant_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    variant_logger.addHandler(file_handler)
    console.print(f"  Variant strategy log: {log_path}")


def _run_export(
    entries: list[WordEntry],
    variants: dict[str, list[str]],
    sources: dict[str, bool],
    overrides_path: str | None,
    exclusion_list: str | None,
    no_exclusion_list: bool,
    min_sources: int,
    vocab_limit: int,
    trie_dir: Path,
) -> None:
    """Apply overrides, exclusions, filters, and export dataset."""
    # Apply manual overrides
    overrides_file = Path(overrides_path) if overrides_path else None
    overrides = load_overrides(overrides_file)
    if overrides:
        entries, variants = apply_overrides(entries, variants, overrides)

    # Apply word exclusion list
    exclusion_path = (
        None if no_exclusion_list
        else Path(exclusion_list) if exclusion_list
        else _cfg.get_exclusions_path()
    )
    exclusion_words = load_exclusion_list(exclusion_path)
    if exclusion_words:
        console.print(f"\n{'=' * 60}")
        console.print("Word Exclusion List")
        console.print(f"{'=' * 60}")
        entries = apply_exclusion_list(
            entries, exclusion_words, set(overrides.keys()),
        )

    # Apply dataset filters
    console.print(f"\n{'=' * 60}")
    console.print("Dataset Filtering")
    console.print(f"{'=' * 60}")
    entries, variants = filter_dataset(
        entries, variants, overrides,
        min_source_count=min_sources,
        vocab_limit=vocab_limit,
    )

    # Build and export
    console.print(f"\n{'=' * 60}")
    console.print("Export")
    console.print(f"{'=' * 60}")

    sources_used = sorted(
        name for name, on in sources.items()
        if on and any(name in e.sources for e in entries)
    )

    dataset = build_trie_dataset(entries, variants)
    trie_dir.mkdir(parents=True, exist_ok=True)
    export_json(dataset, sources_used, trie_dir / "trie_dataset.json")
    export_csv(dataset, trie_dir / "trie_dataset.csv")

    print_stats(dataset)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Trie generation pipeline for THAIME."""


# ---------------------------------------------------------------------------
# run — full pipeline
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--sources", default=None, help="Comma-separated sources (default: all configured)")
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers}, 0=sequential)")
@click.option("--max-variants", default=_cfg.max_variants_per_word, type=int, help=f"Max variants per word (default: {_cfg.max_variants_per_word})")
@click.option("--vocab-limit", default=_cfg.vocab_limit, type=int, help=f"Top N words by frequency (default: {_cfg.vocab_limit}, 0=no limit)")
@click.option("--min-sources", default=_cfg.min_source_count, type=int, help=f"Minimum corpus source count (default: {_cfg.min_source_count})")
@click.option("--exclusion-list", default=None, type=click.Path(), help="Path to word exclusion list (default: latest)")
@click.option("--no-exclusion-list", is_flag=True, help="Disable word exclusion list")
@click.option("--overrides", default=None, type=click.Path(), help="Path to overrides YAML (default: latest)")
@click.option("--no-cache", is_flag=True, help="Ignore cached files, force full rebuild")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
@click.pass_context
def run(ctx, sources, workers, max_variants, vocab_limit, min_sources,
        exclusion_list, no_exclusion_list, overrides, no_cache, output_dir):
    """Run the full pipeline: wordlist, variants, export."""
    # Inherit global --no-cache / --workers if set
    parent = ctx.parent.obj if ctx.parent and ctx.parent.obj else {}
    if parent.get("no_cache"):
        no_cache = True
    if parent.get("workers") is not None:
        workers = parent["workers"]

    sources_dict = _parse_sources(sources)
    base = Path(output_dir) if output_dir else _cfg.output_dir
    wordlist_dir = base / "wordlist"
    variants_dir = base / "variants"
    trie_dir = base / "trie"
    wordlist_dir.mkdir(parents=True, exist_ok=True)
    variants_dir.mkdir(parents=True, exist_ok=True)
    _setup_variant_logging(variants_dir)

    wordlist_path = wordlist_dir / "wordlist.csv"
    variants_path = variants_dir / "variants.json"
    checkpoint_path = variants_dir / ".variants_checkpoint.json"

    # Step 1: Word list
    console.print("=" * 60)
    console.print("Step 1: Word List Assembly")
    console.print("=" * 60)

    use_wordlist_cache = not no_cache and check_cache(wordlist_path, "wordlist.csv")
    if use_wordlist_cache:
        entries = load_wordlist_csv(wordlist_path)
        console.print(f"  Loaded {len(entries):,} words from cache")
        wordlist_was_cached = True
    else:
        entries = assemble_wordlist(sources=sources_dict, num_workers=workers)
        if not entries:
            console.print("[red]ERROR: No words assembled. Check that corpora are downloaded.[/red]")
            sys.exit(1)
        save_wordlist_csv(entries, wordlist_path)
        wordlist_was_cached = False

    # Step 2: Variant generation
    console.print(f"\n{'=' * 60}")
    console.print("Step 2: Variant Generation")
    console.print(f"{'=' * 60}")

    use_variant_cache = (
        not no_cache
        and wordlist_was_cached
        and check_cache(variants_path, "variants.json")
    )
    if use_variant_cache:
        variants = _load_variants_checkpoint(variants_path)
        console.print(f"  Loaded {len(variants):,} word variants from cache")
    else:
        variants = run_variant_generation(
            entries,
            max_variants=max_variants,
            num_workers=workers,
            checkpoint_path=checkpoint_path,
        )
        _save_variants_checkpoint(variants, variants_path)
        console.print(f"  Variants saved to {variants_path}")

    # Steps 3-4: Export
    _run_export(
        entries, variants, sources_dict,
        overrides, exclusion_list, no_exclusion_list,
        min_sources, vocab_limit, trie_dir,
    )

    console.print(f"\n{'=' * 60}")
    console.print("Pipeline complete!")
    console.print(f"{'=' * 60}")
    console.print(f"  Output directory: {base}")


# ---------------------------------------------------------------------------
# wordlist — Step 1 only
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--sources", default=None, help="Comma-separated sources (default: all configured)")
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers})")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
def wordlist(sources, workers, output_dir):
    """Step 1: Assemble word list from corpora."""
    sources_dict = _parse_sources(sources)
    wordlist_dir = _resolve_output_dir(output_dir, "wordlist")
    wordlist_path = wordlist_dir / "wordlist.csv"

    console.print("=" * 60)
    console.print("Step 1: Word List Assembly")
    console.print("=" * 60)

    entries = assemble_wordlist(sources=sources_dict, num_workers=workers)
    if not entries:
        console.print("[red]ERROR: No words assembled.[/red]")
        sys.exit(1)
    save_wordlist_csv(entries, wordlist_path)

    console.print("\nWord list assembly complete.")


# ---------------------------------------------------------------------------
# variant — Step 2 only
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers}, 0=sequential)")
@click.option("--max-variants", default=_cfg.max_variants_per_word, type=int, help=f"Max variants per word (default: {_cfg.max_variants_per_word})")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
def variant(workers, max_variants, output_dir):
    """Step 2: Generate romanization variants. Requires cached wordlist.csv."""
    base = Path(output_dir) if output_dir else _cfg.output_dir
    wordlist_dir = base / "wordlist"
    variants_dir = base / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    _setup_variant_logging(variants_dir)

    wordlist_path = wordlist_dir / "wordlist.csv"
    variants_path = variants_dir / "variants.json"
    checkpoint_path = variants_dir / ".variants_checkpoint.json"

    if not wordlist_path.exists():
        console.print(f"[red]ERROR: Cached word list not found at {wordlist_path}[/red]")
        console.print("  Run 'wordlist' first.")
        sys.exit(1)

    console.print("=" * 60)
    console.print("Loading cached word list")
    console.print("=" * 60)
    entries = load_wordlist_csv(wordlist_path)
    console.print(f"  Loaded {len(entries):,} words from {wordlist_path}")

    console.print(f"\n{'=' * 60}")
    console.print("Step 2: Variant Generation")
    console.print(f"{'=' * 60}")

    variants = run_variant_generation(
        entries,
        max_variants=max_variants,
        num_workers=workers,
        checkpoint_path=checkpoint_path,
    )
    _save_variants_checkpoint(variants, variants_path)
    console.print(f"  Variants saved to {variants_path}")

    console.print("\nVariant generation complete.")


# ---------------------------------------------------------------------------
# export — Steps 3-4 only
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--sources", default=None, help="Comma-separated sources (default: all configured)")
@click.option("--exclusion-list", default=None, type=click.Path(), help="Path to word exclusion list (default: latest)")
@click.option("--no-exclusion-list", is_flag=True, help="Disable word exclusion list")
@click.option("--overrides", default=None, type=click.Path(), help="Path to overrides YAML (default: latest)")
@click.option("--vocab-limit", default=_cfg.vocab_limit, type=int, help=f"Top N words by frequency (default: {_cfg.vocab_limit}, 0=no limit)")
@click.option("--min-sources", default=_cfg.min_source_count, type=int, help=f"Minimum corpus source count (default: {_cfg.min_source_count})")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
def export(sources, exclusion_list, no_exclusion_list, overrides,
           vocab_limit, min_sources, output_dir):
    """Steps 3-4: Apply filters and export. Requires cached wordlist.csv and variants.json."""
    sources_dict = _parse_sources(sources)
    base = Path(output_dir) if output_dir else _cfg.output_dir
    wordlist_dir = base / "wordlist"
    variants_dir = base / "variants"
    trie_dir = base / "trie"

    wordlist_path = wordlist_dir / "wordlist.csv"
    variants_path = variants_dir / "variants.json"

    if not wordlist_path.exists():
        console.print(f"[red]ERROR: Cached word list not found at {wordlist_path}[/red]")
        sys.exit(1)
    if not variants_path.exists():
        console.print(f"[red]ERROR: Cached variants not found at {variants_path}[/red]")
        sys.exit(1)

    console.print("=" * 60)
    console.print("Loading cached data")
    console.print("=" * 60)
    entries = load_wordlist_csv(wordlist_path)
    console.print(f"  Loaded {len(entries):,} words from {wordlist_path}")
    variants = _load_variants_checkpoint(variants_path)
    console.print(f"  Loaded {len(variants):,} word variants from {variants_path}")

    _run_export(
        entries, variants, sources_dict,
        overrides, exclusion_list, no_exclusion_list,
        min_sources, vocab_limit, trie_dir,
    )

    console.print(f"\n{'=' * 60}")
    console.print("Export complete!")
    console.print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Register validate and review subcommands
# ---------------------------------------------------------------------------


from pipelines.trie.validate import validate as _validate_cmd
from pipelines.trie.review import review as _review_cmd

cli.add_command(_validate_cmd, "validate")
cli.add_command(_review_cmd, "review")


if __name__ == "__main__":
    cli()
