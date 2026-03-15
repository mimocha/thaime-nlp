"""Word-conversion benchmark generation pipeline — Click CLI.

Consolidates the 4-script benchmark-wordconv pattern into a single
Click subgroup with extract/romanize/review/export subcommands.

Usage:
    python -m pipelines benchmark word-conversion run
    python -m pipelines benchmark word-conversion extract --top-k 500
    python -m pipelines benchmark word-conversion romanize --workers 4
    python -m pipelines benchmark word-conversion review
    python -m pipelines benchmark word-conversion export
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import click

from pipelines.cache import check_cache
from pipelines.config import REPO_ROOT, BenchmarkConfig
from pipelines.console import console
from src.corpora.readers import check_corpus_available, iter_corpus_texts
from src.corpora.tokenizer import tokenize_and_filter
from src.utils.frequency import merge_frequencies, normalize_frequencies

_cfg = BenchmarkConfig()


# ---------------------------------------------------------------------------
# Step 1: Extract word frequencies
# ---------------------------------------------------------------------------


def extract_frequencies(
    corpora: list[str],
    top_k: int,
    output_path: Path,
) -> None:
    """Extract and merge word frequencies from corpora, output top-K."""
    console.print("=" * 60)
    console.print("Step 1: Extract Word Frequencies")
    console.print("=" * 60)

    raw_counters: dict[str, Counter] = {}
    for name in corpora:
        if not check_corpus_available(name):
            console.print(f"  [{name}] Not available, skipping")
            continue
        console.print(f"  [{name}] Reading...")
        counter: Counter = Counter()
        for text in iter_corpus_texts(name):
            counter.update(tokenize_and_filter(text))
        raw_counters[name] = counter
        console.print(f"  [{name}] {len(counter):,} unique words, {sum(counter.values()):,} tokens")

    if not raw_counters:
        console.print("[red]ERROR: No corpora loaded![/red]")
        sys.exit(1)

    # Normalize and merge
    norm_freqs = [normalize_frequencies(c) for c in raw_counters.values()]
    merged = merge_frequencies(norm_freqs)

    console.print(f"\n  Total unique words: {len(merged):,}")
    console.print(f"  Selecting top {top_k} words by weighted frequency...")

    merged_counter = Counter(merged)
    top_words = merged_counter.most_common(top_k)

    # Per-corpus ranks for top-K
    corpus_names = list(raw_counters.keys())
    norm_dicts = {name: normalize_frequencies(raw_counters[name]) for name in corpus_names}

    def _lazy_ranks(norm_freq: dict[str, float], top_set: set[str]) -> dict[str, int]:
        relevant = {w: freq for w, freq in norm_freq.items() if w in top_set}
        sorted_words = sorted(relevant.items(), key=lambda x: x[1], reverse=True)
        return {w: i + 1 for i, (w, _) in enumerate(sorted_words)}

    top_set = {w for w, _ in top_words}
    ranks = {name: _lazy_ranks(norm_dicts[name], top_set) for name in corpus_names}

    # Write CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        header = ["rank", "thai_word", "merged_freq"]
        for name in corpus_names:
            header.append(f"{name}_rank")
        header.append("corpus_count")
        writer.writerow(header)

        for i, (word, freq) in enumerate(top_words):
            row = [i + 1, word, f"{freq:.10f}"]
            corpus_count = 0
            for name in corpus_names:
                r = ranks[name].get(word, "")
                row.append(r)
                if r != "":
                    corpus_count += 1
            row.append(corpus_count)
            writer.writerow(row)

    console.print(f"\n  Output: {output_path} ({len(top_words)} entries)")

    # Show top 10
    console.print(f"\n  Top 10 words:")
    for i, (word, freq) in enumerate(top_words[:10]):
        console.print(f"    {i + 1:3d}. {word}  (freq: {freq:.8f})")


# ---------------------------------------------------------------------------
# Step 2: Generate romanizations
# ---------------------------------------------------------------------------


def _process_single_word(
    thai_word: str, rank: int, corpus_count: int, max_variants: int,
) -> dict:
    """Process a single word: TLTK calls, variant generation, classification."""
    import tltk
    from src.variant_generator import (
        analyze_word,
        generate_word_variants,
        _clean_tltk_output,
        _get_dictionary,
    )
    from pipelines.benchmarks.word_conversion.classify import classify_word

    try:
        base_roman = _clean_tltk_output(tltk.nlp.th2roman(thai_word))
    except Exception:
        base_roman = ""

    if not base_roman:
        return {"status": "failed", "thai_word": thai_word, "rank": rank, "reason": "TLTK empty"}

    syllable_components = analyze_word(thai_word)
    syllable_count = max(1, len(syllable_components))

    variants = generate_word_variants(
        thai_word,
        max_variants,
        _base_roman=base_roman,
        _syllables=syllable_components,
    )

    dictionary = _get_dictionary()
    components: list[dict] = []
    for comp in syllable_components:
        onset_variants = dictionary["onsets"].get(comp.onset, None)
        if onset_variants is None:
            onset_variants = [""] if comp.onset in ("?", "") else [comp.onset]
        vowel_variants = dictionary["vowels"].get(comp.vowel, None)
        if vowel_variants is None:
            vowel_variants = [comp.vowel] if comp.vowel else [""]
        coda_variants = dictionary["codas"].get(comp.coda, None)
        if coda_variants is None:
            coda_variants = [comp.coda] if comp.coda else [""]
        components.append({
            "thai_segment": comp.thai_segment,
            "onset": comp.onset,
            "vowel": comp.vowel,
            "coda": comp.coda,
            "tone": comp.tone,
            "onset_variants": onset_variants,
            "vowel_variants": vowel_variants,
            "coda_variants": coda_variants,
        })

    category, difficulty = classify_word(
        thai_word=thai_word,
        romanization=base_roman,
        variant_count=len(variants),
        merged_rank=rank,
        syllable_count=syllable_count,
    )

    return {
        "status": "ok",
        "thai_word": thai_word,
        "rtgs_romanization": base_roman,
        "variants": variants,
        "variant_count": len(variants),
        "components": components,
        "category": category,
        "difficulty": difficulty,
        "syllable_count": syllable_count,
        "frequency_rank": rank,
        "corpus_count": corpus_count,
        "notes": "",
        "review_status": "pending",
    }


def generate_romanizations(
    input_path: Path,
    output_path: Path,
    top_k: int,
    max_variants: int,
    num_workers: int,
) -> None:
    """Generate romanization variants for top-K words."""
    console.print("=" * 60)
    console.print("Step 2: Generate Romanizations")
    console.print("=" * 60)

    words: list[dict] = []
    with open(input_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append(row)
            if len(words) >= top_k:
                break

    console.print(f"  Loaded {len(words)} words from {input_path}")

    work_items = [
        (wd["thai_word"], int(wd["rank"]), int(wd.get("corpus_count", 0)), max_variants)
        for wd in words
    ]

    entries: list[dict] = []
    failed: list[dict] = []

    start = time.time()
    if num_workers > 1:
        ctx = get_context("fork")
        console.print(f"  Using {num_workers} parallel workers (fork)")
        with ProcessPoolExecutor(max_workers=num_workers, mp_context=ctx) as pool:
            for result in pool.map(_process_single_word, *zip(*work_items), chunksize=100):
                if result["status"] == "ok":
                    result.pop("status")
                    entries.append(result)
                else:
                    result.pop("status")
                    failed.append(result)
    else:
        console.print("  Using sequential processing")
        for i, (thai_word, rank, corpus_count, mv) in enumerate(work_items):
            result = _process_single_word(thai_word, rank, corpus_count, mv)
            if result["status"] == "ok":
                result.pop("status")
                entries.append(result)
            else:
                result.pop("status")
                failed.append(result)
            if (i + 1) % 50 == 0:
                console.print(f"  Processed {i + 1}/{len(words)} words...")

    elapsed = time.time() - start
    console.print(f"\n  Successfully processed: {len(entries)} ({elapsed:.1f}s)")
    console.print(f"  Failed (TLTK errors): {len(failed)}")

    cat_dist = Counter(e["category"] for e in entries)
    diff_dist = Counter(e["difficulty"] for e in entries)
    console.print(f"\n  Category distribution:")
    for cat, count in sorted(cat_dist.items()):
        console.print(f"    {cat}: {count}")
    console.print(f"\n  Difficulty distribution:")
    for diff, count in sorted(diff_dist.items()):
        console.print(f"    {diff}: {count}")

    output_data = {
        "metadata": {
            "version": "v0.4.1-draft",
            "source": "pipeline/benchmark-v2",
            "corpora": _cfg.corpora,
            "weighting": "equal (1/N each)",
            "top_k_input": top_k,
            "total_entries": len(entries),
            "total_failed": len(failed),
        },
        "entries": entries,
        "failed": failed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    console.print(f"\n  Output: {output_path}")


# ---------------------------------------------------------------------------
# Step 4: Export to CSV
# ---------------------------------------------------------------------------


def export_benchmark_csv(
    input_path: Path,
    output_path: Path,
    include_discarded: bool = False,
) -> None:
    """Export reviewed entries to benchmark CSV format."""
    console.print("=" * 60)
    console.print("Step 4: Export to CSV")
    console.print("=" * 60)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]

    if include_discarded:
        accepted = entries
    else:
        accepted = [e for e in entries if e["review_status"] in ("approved", "edited")]

    if not accepted:
        console.print("[red]No approved/edited entries found![/red]")
        status_dist = Counter(e["review_status"] for e in entries)
        for status, count in sorted(status_dist.items()):
            console.print(f"    {status}: {count}")
        sys.exit(1)

    rows: list[dict] = []
    for entry in accepted:
        for variant in entry["variants"]:
            rows.append({
                "latin_input": variant,
                "expected_thai": entry["thai_word"],
                "category": entry["category"],
                "difficulty": entry["difficulty"],
                "notes": entry.get("notes", ""),
            })

    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    rows.sort(key=lambda r: (
        r["category"],
        difficulty_order.get(r["difficulty"], 9),
        r["latin_input"],
    ))

    unique_thai = len(set(r["expected_thai"] for r in rows))
    console.print(f"  Accepted entries (Thai words):  {len(accepted)}")
    console.print(f"  Total CSV rows (variants):      {len(rows)}")
    console.print(f"  Unique Thai words:              {unique_thai}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["latin_input", "expected_thai", "category", "difficulty", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"\n  Written to: {output_path}")
    console.print(f"  Total rows: {len(rows)}")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Word-conversion benchmark generation pipeline."""


@cli.command()
@click.option("--top-k", default=_cfg.top_k, type=int, help=f"Number of top words (default: {_cfg.top_k})")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
def extract(top_k, output_dir):
    """Step 1: Extract word frequencies from corpora."""
    base = Path(output_dir) if output_dir else _cfg.benchmark_dir
    base.mkdir(parents=True, exist_ok=True)
    extract_frequencies(_cfg.corpora, top_k, base / "word_frequencies.csv")


@cli.command()
@click.option("--top-k", default=1000, type=int, help="Number of top words to process (default: 1000)")
@click.option("--max-variants", default=_cfg.max_variants, type=int, help=f"Max variants per word (default: {_cfg.max_variants})")
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers})")
@click.option("--input", "input_path", default=None, type=click.Path(), help="Input word frequencies CSV")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
def romanize(top_k, max_variants, workers, input_path, output_dir):
    """Step 2: Generate romanization variants."""
    base = Path(output_dir) if output_dir else _cfg.benchmark_dir
    inp = Path(input_path) if input_path else base / "word_frequencies.csv"
    if not inp.exists():
        console.print(f"[red]ERROR: {inp} not found. Run 'extract' first.[/red]")
        sys.exit(1)
    generate_romanizations(inp, base / "draft_benchmark.json", top_k, max_variants, workers)


@cli.command()
@click.option("--input", "input_path", default=None, type=click.Path(), help="Input JSON path")
@click.option("--output", "output_path", default=None, type=click.Path(), help="Save path for reviewed data")
@click.option("--stats", is_flag=True, help="Show statistics and exit")
def review(input_path, output_path, stats):
    """Step 3: Interactive review of generated entries."""
    from pipelines.benchmarks.word_conversion.review_cli import (
        display_stats, load_data, review_loop, save_data,
    )

    base = _cfg.benchmark_dir
    inp = Path(input_path) if input_path else base / "draft_benchmark.json"
    save_path = Path(output_path) if output_path else base / "reviewed_benchmark.json"

    if save_path.exists():
        console.print(f"  Resuming from {save_path}")
        data = load_data(save_path)
    elif inp.exists():
        console.print(f"  Loading from {inp}")
        data = load_data(inp)
    else:
        console.print(f"[red]ERROR: No input file found at {inp}[/red]")
        console.print(f"  Run 'romanize' first.")
        sys.exit(1)

    if stats:
        display_stats(data["entries"])
        return

    review_loop(data, save_path)


@cli.command("export")
@click.option("--input", "input_path", default=None, type=click.Path(), help="Input reviewed JSON")
@click.option("--output", "output_path", default=None, type=click.Path(), help="Output CSV path")
@click.option("--include-discarded", is_flag=True, help="Include discarded entries")
def export_cmd(input_path, output_path, include_discarded):
    """Step 4: Export reviewed entries to benchmark CSV."""
    base = _cfg.benchmark_dir
    inp = Path(input_path) if input_path else base / "reviewed_benchmark.json"
    out = Path(output_path) if output_path else REPO_ROOT / "benchmarks" / "word-conversion" / "output.csv"

    if not inp.exists():
        console.print(f"[red]ERROR: {inp} not found. Run 'review' first.[/red]")
        sys.exit(1)

    export_benchmark_csv(inp, out, include_discarded)


@cli.command()
@click.option("--top-k", default=_cfg.top_k, type=int, help=f"Number of top words (default: {_cfg.top_k})")
@click.option("--max-variants", default=_cfg.max_variants, type=int, help=f"Max variants per word (default: {_cfg.max_variants})")
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Worker processes (default: {_cfg.num_workers})")
@click.option("--output-dir", default=None, type=click.Path(), help="Base output directory")
@click.option("--no-cache", is_flag=True, help="Force re-extraction even if cached")
@click.pass_context
def run(ctx, top_k, max_variants, workers, output_dir, no_cache):
    """Run full pipeline: extract, romanize (review and export are manual)."""
    parent = ctx.parent
    while parent:
        if parent.obj and parent.obj.get("no_cache"):
            no_cache = True
        if parent.obj and parent.obj.get("workers") is not None:
            workers = parent.obj["workers"]
        parent = parent.parent

    base = Path(output_dir) if output_dir else _cfg.benchmark_dir
    base.mkdir(parents=True, exist_ok=True)

    freq_path = base / "word_frequencies.csv"
    draft_path = base / "draft_benchmark.json"

    if not no_cache and check_cache(freq_path, "word_frequencies.csv"):
        console.print("  Using cached word frequencies")
    else:
        extract_frequencies(_cfg.corpora, top_k, freq_path)

    if not no_cache and check_cache(draft_path, "draft_benchmark.json"):
        console.print("  Using cached draft benchmark")
    else:
        generate_romanizations(freq_path, draft_path, top_k * 2, max_variants, workers)

    console.print(f"\n{'=' * 60}")
    console.print("Automated steps complete!")
    console.print(f"{'=' * 60}")
    console.print(f"  Next steps:")
    console.print(f"    python -m pipelines benchmark word-conversion review")
    console.print(f"    python -m pipelines benchmark word-conversion export")


if __name__ == "__main__":
    cli()
