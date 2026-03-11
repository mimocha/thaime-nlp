"""Trie generation pipeline — main entry point.

Assembles a Thai word list from multiple sources, generates romanization
variants for each word using the dictionary-driven variant generator,
and exports a trie-ready dataset.

Usage:
    python -m pipelines.trie.generate
    python -m pipelines.trie.generate --sources wisesight,wongnai,pythainlp
    python -m pipelines.trie.generate --workers 8
    python -m pipelines.trie.generate --vocab-limit 10000 --min-sources 2
    python -m pipelines.trie.generate --exclusion-list data/dictionaries/word_exclusions/exclusions-v1.0.0.txt
    python -m pipelines.trie.generate --overrides data/dictionaries/word_overrides/overrides-v1.0.0.yaml
    python -m pipelines.trie.generate --wordlist-only
    python -m pipelines.trie.generate --variant-only
    python -m pipelines.trie.generate --export-only
    python -m pipelines.trie.generate --no-cache
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path

import yaml

from pipelines.trie.config import (
    EXCLUSIONS_PATH,
    LOG_INTERVAL,
    MAX_LENGTH_RATIO,
    MAX_VARIANTS_PER_WORD,
    MIN_FREQUENCY,
    MIN_SOURCE_COUNT,
    NUM_WORKERS,
    OUTPUT_DIR,
    OVERRIDES_PATH,
    SOURCES,
    VOCAB_LIMIT,
)
from pipelines.trie.wordlist import (
    WordEntry,
    assemble_wordlist,
    load_wordlist_csv,
    save_wordlist_csv,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Variant generation (single word — used by worker processes)
# ---------------------------------------------------------------------------


def _generate_variants_for_word(args: tuple[str, int]) -> tuple[str, int, list[str]]:
    """Generate variants for a single word. Used as multiprocessing target.

    Args:
        args: Tuple of (thai_word, max_variants).

    Returns:
        Tuple of (thai_word, word_id_placeholder, variants_list).
        word_id is set to -1 here; assigned later by the caller.
    """
    thai_word, max_variants = args
    try:
        from src.variant_generator import generate_word_variants
        variants = generate_word_variants(thai_word, max_variants=max_variants)
    except Exception as e:
        logger.warning("Failed to generate variants for %s: %s", thai_word, e)
        variants = []
    return (thai_word, -1, variants)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _save_variants_checkpoint(
    results: dict[str, list[str]], path: Path,
) -> None:
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


def load_overrides(path: Path = OVERRIDES_PATH) -> dict[str, list[str]]:
    """Load manual romanization overrides from YAML.

    Returns:
        Dict mapping thai_word -> list of romanization variants.
        Returns empty dict if the file doesn't exist or has no entries.
    """
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
    """Merge manual overrides into the word list and variants.

    Override words that already exist in entries get their variants
    replaced. Override words NOT in entries are appended (they may
    have been removed by word filters).

    Returns:
        Updated (entries, variants) tuple.
    """
    if not overrides:
        return entries, variants

    existing_words = {e.word for e in entries}
    added = 0

    for word, romanizations in overrides.items():
        variants[word] = romanizations
        if word not in existing_words:
            # Append as a low-frequency entry from the "overrides" source
            entries.append(WordEntry(
                word=word, frequency=0.0, sources={"overrides"},
            ))
            existing_words.add(word)
            added += 1

    replaced = len(overrides) - added
    print(f"  Manual overrides applied: {len(overrides)} words "
          f"({replaced} replaced, {added} new)")

    return entries, variants


# ---------------------------------------------------------------------------
# Word exclusion list
# ---------------------------------------------------------------------------


def load_exclusion_list(path: Path | None) -> set[str]:
    """Load a word exclusion list from a plain-text file.

    Each line is one Thai word. Lines starting with '#' are ignored.
    Returns an empty set if path is None or the file doesn't exist.
    """
    if path is None:
        return set()

    if not path.exists():
        print(f"  WARNING: Exclusion list not found at {path}")
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
    """Remove words on the exclusion list from entries.

    Override words are exempt from exclusion.

    Returns:
        Filtered entries list.
    """
    if not exclusion_words:
        return entries

    before = len(entries)
    filtered = [
        e for e in entries
        if e.word not in exclusion_words or e.word in override_words
    ]
    removed = before - len(filtered)

    print(f"  Word exclusion list: {removed:,} words removed "
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
    min_source_count: int = MIN_SOURCE_COUNT,
    min_frequency: float = MIN_FREQUENCY,
    max_length_ratio: float = MAX_LENGTH_RATIO,
    vocab_limit: int = VOCAB_LIMIT,
) -> tuple[list[WordEntry], dict[str, list[str]]]:
    """Apply quality filters to the word list after variant generation.

    Filters applied in order:
      1. Source count: words must appear in >= min_source_count corpora.
         Words from pythainlp-only and override words are exempt.
      2. Frequency: words must have frequency >= min_frequency.
         Override words are exempt.
      3. Romanization sanity: words where
         (thai_base_len / min_romanization_len) > max_length_ratio
         are removed as likely TLTK failures. Override words are exempt.
      4. Empty variants: words with zero romanization variants are removed.
      5. Vocabulary limit: if vocab_limit > 0, keep only the top N words
         by frequency after all other filters. Override words are always
         kept regardless of the limit.

    Returns:
        Filtered (entries, variants) tuple.
    """
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

    # Filter 5: vocabulary limit — keep top N by frequency, overrides always kept
    removed_vocab_limit = 0
    if vocab_limit > 0 and len(filtered) > vocab_limit:
        # Separate overrides from regular entries (overrides always kept)
        override_entries = [e for e in filtered if e.word in override_words]
        regular_entries = [e for e in filtered if e.word not in override_words]

        # Sort regular entries by frequency (descending) and truncate
        regular_entries.sort(key=lambda e: e.frequency, reverse=True)
        # Account for override slots when computing how many regular words to keep
        regular_limit = max(0, vocab_limit - len(override_entries))
        removed_vocab_limit = max(0, len(regular_entries) - regular_limit)
        regular_entries = regular_entries[:regular_limit]

        # Re-sort the combined list by frequency (descending) for consistent ordering
        filtered = override_entries + regular_entries
        filtered.sort(key=lambda e: e.frequency, reverse=True)

    # Clean up variants dict to match filtered entries
    kept_words = {e.word for e in filtered}
    filtered_variants = {w: v for w, v in variants.items() if w in kept_words}

    print(f"\n  Dataset filtering:")
    print(f"    Before:                {before:>8,} words")
    print(f"    Removed (source < {min_source_count}):  {removed_source:>8,}")
    print(f"    Removed (freq < {min_frequency:.0e}): {removed_freq:>8,}")
    print(f"    Removed (ratio > {max_length_ratio}):  {removed_ratio:>8,}")
    print(f"    Removed (0 variants):  {removed_empty:>8,}")
    print(f"    After quality filters: {after_filters:>8,} words")
    if vocab_limit > 0:
        print(f"    Vocab limit:           {vocab_limit:>8,}")
        print(f"    Removed (vocab limit): {removed_vocab_limit:>8,}")
    print(f"    Final vocabulary:      {len(filtered):>8,} words")

    return filtered, filtered_variants


# Size of each chunk for chunked multiprocessing. A fresh process pool is
# created per chunk to limit memory growth and contain worker crashes.
_CHUNK_SIZE = 5000


def run_variant_generation(
    entries: list[WordEntry],
    max_variants: int = MAX_VARIANTS_PER_WORD,
    num_workers: int = NUM_WORKERS,
    checkpoint_path: Path | None = None,
) -> dict[str, list[str]]:
    """Generate romanization variants for all words in the word list.

    Processes words in chunks with a fresh process pool per chunk to limit
    memory growth. Saves checkpoints after each chunk so progress survives
    crashes.

    Args:
        entries: Assembled word list.
        max_variants: Maximum variants per word.
        num_workers: Number of worker processes (0 for sequential).
        checkpoint_path: Path for checkpoint file. If it exists, already-
            processed words are skipped.

    Returns:
        Dict mapping thai_word -> list of romanization variants.
    """
    words = [e.word for e in entries]
    total = len(words)

    # Load checkpoint if available
    results: dict[str, list[str]] = {}
    if checkpoint_path and checkpoint_path.exists():
        results = _load_variants_checkpoint(checkpoint_path)
        print(f"  Loaded checkpoint: {len(results):,} words already processed")

    # Filter to words not yet processed
    remaining = [w for w in words if w not in results]
    if not remaining:
        print(f"  All {total:,} words already processed (from checkpoint)")
        _print_variant_stats(results, total)
        return results

    print(f"\n  Generating variants for {len(remaining):,} remaining words "
          f"(of {total:,} total, max_variants={max_variants}, workers={num_workers})...")

    start = time.time()
    processed_before = len(results)
    failures = sum(1 for v in results.values() if not v)

    if num_workers > 0:
        # Process in chunks, creating a fresh pool per chunk to contain
        # memory growth and survive individual worker crashes.
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
                print(f"\n  WARNING: Pool crashed on chunk starting at "
                      f"word {chunk_start + processed_before:,}: {e}")
                print(f"  Saving checkpoint with {len(results):,} words processed...")
                if checkpoint_path:
                    _save_variants_checkpoint(results, checkpoint_path)
                print(f"  Re-run the pipeline to resume from checkpoint.")
                raise

            # Progress report after each chunk
            done = len(results) - processed_before
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            print(
                f"    [{done + processed_before:,}/{total:,}] "
                f"{rate:.0f} words/sec, {failures} failures"
            )

            # Save checkpoint after each chunk
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
            if (i + 1) % LOG_INTERVAL == 0:
                elapsed = time.time() - start
                rate = (i + 1) / elapsed
                print(
                    f"    [{i + 1 + processed_before:,}/{total:,}] "
                    f"{rate:.0f} words/sec, {failures} failures"
                )
                if checkpoint_path:
                    _save_variants_checkpoint(results, checkpoint_path)

    elapsed = time.time() - start
    print(f"  Variant generation complete in {elapsed:.1f}s")
    _print_variant_stats(results, total)

    # Clean up checkpoint on success
    if checkpoint_path and checkpoint_path.exists():
        checkpoint_path.unlink()
        print(f"  Checkpoint cleaned up")

    return results


def _print_variant_stats(results: dict[str, list[str]], total: int) -> None:
    """Print summary statistics for variant generation results."""
    failures = sum(1 for v in results.values() if not v)
    print(f"    Words processed: {len(results):,}")
    print(f"    Failures (0 variants): {failures:,} "
          f"({failures * 100 / total:.1f}%)")

    variant_counts = [len(v) for v in results.values() if v]
    if variant_counts:
        avg = sum(variant_counts) / len(variant_counts)
        variant_counts_sorted = sorted(variant_counts)
        median = variant_counts_sorted[len(variant_counts_sorted) // 2]
        print(f"    Avg variants/word: {avg:.1f}")
        print(f"    Median variants/word: {median}")
        print(f"    Max variants/word: {max(variant_counts)}")


def build_trie_dataset(
    entries: list[WordEntry],
    variants: dict[str, list[str]],
) -> list[dict]:
    """Build the trie dataset entries with word IDs.

    Word IDs are assigned by frequency rank (most frequent = 0).

    Returns:
        List of entry dicts ready for export.
    """
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
    # Compute statistics
    total_keys = sum(len(e["romanizations"]) for e in dataset)
    all_keys: set[str] = set()
    for e in dataset:
        all_keys.update(e["romanizations"])

    output = {
        "metadata": {
            "version": "0.1.0",
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
    print(f"  JSON exported to {path} ({size_mb:.1f} MB)")


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
    print(f"  CSV exported to {path} ({row_count:,} rows, {size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Statistics report
# ---------------------------------------------------------------------------


def print_stats(dataset: list[dict]) -> None:
    """Print summary statistics for the trie dataset."""
    total_words = len(dataset)
    variant_counts = [len(e["romanizations"]) for e in dataset]
    total_keys = sum(variant_counts)

    # Unique romanization keys
    all_keys: set[str] = set()
    for e in dataset:
        all_keys.update(e["romanizations"])

    print(f"\n{'=' * 60}")
    print("Trie Dataset Statistics")
    print(f"{'=' * 60}")
    print(f"  Vocabulary size:          {total_words:>10,}")
    print(f"  Total romanization keys:  {total_keys:>10,}")
    print(f"  Unique romanization keys: {len(all_keys):>10,}")

    if variant_counts:
        avg = total_keys / total_words
        sorted_vc = sorted(variant_counts)
        median = sorted_vc[len(sorted_vc) // 2]
        print(f"\n  Variants per word:")
        print(f"    Average: {avg:.1f}")
        print(f"    Median:  {median}")
        print(f"    Min:     {min(variant_counts)}")
        print(f"    Max:     {max(variant_counts)}")

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

    print(f"\n  Variant count distribution:")
    for label, count in buckets.items():
        pct = count * 100 / total_words if total_words else 0
        print(f"    {label:>5} variants: {count:>8,} words ({pct:5.1f}%)")

    # Collision report: romanization keys mapping to multiple Thai words
    key_to_words: dict[str, list[str]] = {}
    for e in dataset:
        for key in e["romanizations"]:
            key_to_words.setdefault(key, []).append(e["thai"])

    collisions = {k: v for k, v in key_to_words.items() if len(v) > 1}
    if collisions:
        print(f"\n  Romanization key collisions:")
        print(f"    Keys mapping to 2+ Thai words: {len(collisions):,}")
        # Show top collisions by number of words
        top_collisions = sorted(
            collisions.items(), key=lambda x: len(x[1]), reverse=True
        )[:10]
        for key, words in top_collisions:
            print(f"    '{key}' -> {len(words)} words: {', '.join(words[:5])}")
            if len(words) > 5:
                print(f"      ... and {len(words) - 5} more")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate trie dataset from Thai word list."
    )
    parser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="Comma-separated list of sources (default: all configured)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=NUM_WORKERS,
        help=f"Number of worker processes (default: {NUM_WORKERS}, 0=sequential)",
    )
    parser.add_argument(
        "--max-variants",
        type=int,
        default=MAX_VARIANTS_PER_WORD,
        help=f"Max variants per word (default: {MAX_VARIANTS_PER_WORD})",
    )
    parser.add_argument(
        "--vocab-limit",
        type=int,
        default=VOCAB_LIMIT,
        help=f"Keep top N words by frequency after filtering (default: {VOCAB_LIMIT}, 0=no limit)",
    )
    parser.add_argument(
        "--min-sources",
        type=int,
        default=MIN_SOURCE_COUNT,
        help=f"Minimum corpus source count (default: {MIN_SOURCE_COUNT})",
    )
    parser.add_argument(
        "--exclusion-list",
        type=str,
        default=str(EXCLUSIONS_PATH) if EXCLUSIONS_PATH else None,
        help="Path to word exclusion list (default: from config, None=disabled)",
    )
    parser.add_argument(
        "--no-exclusion-list",
        action="store_true",
        help="Disable word exclusion list even if configured",
    )
    parser.add_argument(
        "--overrides",
        type=str,
        default=str(OVERRIDES_PATH),
        help=f"Path to overrides YAML (default: {OVERRIDES_PATH})",
    )
    # Mutually exclusive step flags
    step_group = parser.add_mutually_exclusive_group()
    step_group.add_argument(
        "--wordlist-only",
        action="store_true",
        help="Run step 1 only (word list assembly). Always rebuilds.",
    )
    step_group.add_argument(
        "--variant-only",
        action="store_true",
        help="Run step 2 only (variant generation). Requires cached wordlist.csv.",
    )
    step_group.add_argument(
        "--export-only",
        action="store_true",
        help="Run steps 3-4 only (export). Requires cached wordlist.csv and variants.json.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore cached intermediate files (wordlist.csv, variants.json), forcing a full rebuild.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    # Parse sources
    sources = dict(SOURCES)
    if args.sources:
        sources = {name: False for name in sources}
        for name in args.sources.split(","):
            name = name.strip()
            if name in sources:
                sources[name] = True
            else:
                print(f"WARNING: Unknown source '{name}'")
                sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up logging — variant generator INFO messages go to a log file
    # so we can review words that needed non-standard generation strategies.
    log_path = output_dir / "variant_strategies.log"
    variant_logger = logging.getLogger("src.variant_generator")
    variant_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    variant_logger.addHandler(file_handler)
    print(f"  Variant strategy log: {log_path}")

    wordlist_path = output_dir / "wordlist.csv"
    variants_path = output_dir / "variants.json"
    checkpoint_path = output_dir / ".variants_checkpoint.json"

    run_step1 = not args.variant_only and not args.export_only
    run_step2 = not args.wordlist_only and not args.export_only
    run_export = not args.wordlist_only and not args.variant_only

    # -----------------------------------------------------------------------
    # Step 1: Assemble word list
    # -----------------------------------------------------------------------
    if run_step1:
        print("=" * 60)
        print("Step 1: Word List Assembly")
        print("=" * 60)

        use_wordlist_cache = (
            wordlist_path.exists()
            and not args.wordlist_only
            and not args.no_cache
        )
        if use_wordlist_cache:
            print(f"  Found existing word list at {wordlist_path}")
            entries = load_wordlist_csv(wordlist_path)
            print(f"  Loaded {len(entries):,} words from cache")
            wordlist_was_cached = True
        else:
            entries = assemble_wordlist(sources=sources)
            if not entries:
                print("ERROR: No words assembled. Check that corpora are downloaded.")
                sys.exit(1)
            save_wordlist_csv(entries, wordlist_path)
            wordlist_was_cached = False

        if args.wordlist_only:
            print("\n--wordlist-only: Stopping after word list assembly.")
            return
    else:
        # --variant-only or --export-only: load cached wordlist
        if not wordlist_path.exists():
            print(f"ERROR: Cached word list not found at {wordlist_path}")
            print("  Run without --variant-only/--export-only first to generate it.")
            sys.exit(1)
        print("=" * 60)
        print("Loading cached word list")
        print("=" * 60)
        entries = load_wordlist_csv(wordlist_path)
        print(f"  Loaded {len(entries):,} words from {wordlist_path}")
        wordlist_was_cached = True

    # -----------------------------------------------------------------------
    # Step 2: Variant generation
    # -----------------------------------------------------------------------
    if run_step2:
        print(f"\n{'=' * 60}")
        print("Step 2: Variant Generation")
        print(f"{'=' * 60}")

        # Check for cached variants.json (skip if --no-cache or wordlist was rebuilt)
        use_variant_cache = (
            variants_path.exists()
            and not args.no_cache
            and not args.variant_only  # --variant-only always regenerates
            and wordlist_was_cached
        )
        if use_variant_cache:
            print(f"  Found existing variants at {variants_path}")
            variants = _load_variants_checkpoint(variants_path)
            print(f"  Loaded {len(variants):,} word variants from cache")
        else:
            variants = run_variant_generation(
                entries,
                max_variants=args.max_variants,
                num_workers=args.workers,
                checkpoint_path=checkpoint_path,
            )
            # Save persistent variants file
            _save_variants_checkpoint(variants, variants_path)
            print(f"  Variants saved to {variants_path}")

        if args.variant_only:
            print("\n--variant-only: Stopping after variant generation.")
            return
    else:
        # --export-only: load cached variants
        if not variants_path.exists():
            print(f"ERROR: Cached variants not found at {variants_path}")
            print("  Run --variant-only or full pipeline first to generate it.")
            sys.exit(1)
        print(f"\n{'=' * 60}")
        print("Loading cached variants")
        print(f"{'=' * 60}")
        variants = _load_variants_checkpoint(variants_path)
        print(f"  Loaded {len(variants):,} word variants from {variants_path}")

    # -----------------------------------------------------------------------
    # Apply manual overrides
    # -----------------------------------------------------------------------
    overrides_path = Path(args.overrides)
    overrides = load_overrides(overrides_path)
    if overrides:
        entries, variants = apply_overrides(entries, variants, overrides)

    # -----------------------------------------------------------------------
    # Apply word exclusion list
    # -----------------------------------------------------------------------
    exclusion_path = (
        None if args.no_exclusion_list
        else Path(args.exclusion_list) if args.exclusion_list
        else None
    )
    exclusion_words = load_exclusion_list(exclusion_path)
    if exclusion_words:
        print(f"\n{'=' * 60}")
        print("Word Exclusion List")
        print(f"{'=' * 60}")
        entries = apply_exclusion_list(
            entries, exclusion_words, set(overrides.keys()),
        )

    # -----------------------------------------------------------------------
    # Apply dataset filters
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Dataset Filtering")
    print(f"{'=' * 60}")
    entries, variants = filter_dataset(
        entries, variants, overrides,
        min_source_count=args.min_sources,
        vocab_limit=args.vocab_limit,
    )

    # -----------------------------------------------------------------------
    # Step 3: Build and export trie dataset
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Step 3: Export")
    print(f"{'=' * 60}")

    sources_used = sorted(
        name for name, on in sources.items()
        if on and any(name in e.sources for e in entries)
    )

    dataset = build_trie_dataset(entries, variants)

    export_json(dataset, sources_used, output_dir / "trie_dataset.json")
    export_csv(dataset, output_dir / "trie_dataset.csv")

    # -----------------------------------------------------------------------
    # Step 4: Statistics
    # -----------------------------------------------------------------------
    print_stats(dataset)

    print(f"\n{'=' * 60}")
    print("Pipeline complete!")
    print(f"{'=' * 60}")
    print(f"  Output directory: {output_dir}")


if __name__ == "__main__":
    main()
