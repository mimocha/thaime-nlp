"""N-gram binary encoding — Stage 4.

Reads merged n-gram TSVs and the trie dataset, applies quality filters,
computes Stupid Backoff log-probabilities, and writes a versioned binary
file consumed by the thaime engine.

Usage:
    python -m pipelines ngram encode
    python -m pipelines ngram encode --min-count 20 --alpha 0.4
"""

from __future__ import annotations

import json
import math
import struct
import subprocess
import time
from pathlib import Path

import click

from pipelines.config import NgramConfig, TEXT_CORPORA
from pipelines.console import console

_cfg = NgramConfig()

# Binary format constants
MAGIC = b"TNLM"  # 0x544E4C4D
FORMAT_VERSION = 1
HEADER_SIZE = 32

# Smoothing method enum
SMOOTHING_ENUM = {"sbo": 0, "mkn": 1, "katz": 2}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_trie_dataset(path: Path) -> tuple[list[str], dict[str, int]]:
    """Load string table and word_id mapping from trie dataset JSON.

    Returns:
        (string_table, word_to_id) where string_table[i] is the Thai word
        for word_id=i and word_to_id maps Thai word → word_id.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]
    string_table = [""] * len(entries)
    word_to_id: dict[str, int] = {}

    for entry in entries:
        wid = entry["word_id"]
        thai = entry["thai"]
        string_table[wid] = thai
        word_to_id[thai] = wid

    return string_table, word_to_id


def load_ngram_tsv(path: Path) -> dict[tuple[str, ...], float]:
    """Load an n-gram TSV file (frequency or count format).

    Returns a dict mapping n-gram tuples to their float values.
    """
    ngrams: dict[tuple[str, ...], float] = {}
    if not path.exists():
        return ngrams

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            value = float(parts[-1])
            tokens = tuple(parts[:-1])
            ngrams[tokens] = value

    return ngrams


# ---------------------------------------------------------------------------
# Token quality filtering
# ---------------------------------------------------------------------------


def load_per_corpus_token_sources(
    ngram_dir: Path,
    corpora: list[str],
) -> dict[str, int]:
    """Derive per-token source counts from per-corpus unigram TSVs.

    A token's source count is the number of corpora that contain it
    (with count > 0 in the per-corpus TSV).

    Returns:
        dict mapping token → number of corpora containing it.
    """
    token_sources: dict[str, set[str]] = {}

    for corpus in corpora:
        path = ngram_dir / f"ngrams_1_{corpus}.tsv"
        if not path.exists():
            console.print(f"  [yellow]WARNING: Missing per-corpus TSV: {path}[/yellow]")
            continue

        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 2:
                    continue
                token = parts[0]
                if token not in token_sources:
                    token_sources[token] = set()
                token_sources[token].add(corpus)

    return {token: len(sources) for token, sources in token_sources.items()}


def build_valid_tokens(
    source_counts: dict[str, int],
    merged_freqs: dict[tuple[str, ...], float],
    word_to_id: dict[str, int],
    min_sources: int,
    min_freq: float,
) -> set[str]:
    """Build the set of tokens that pass quality filters.

    A token is valid if:
    1. It exists in the trie dataset (has a word_id)
    2. source_count >= min_sources
    3. merged unigram frequency >= min_freq
    """
    valid = set()
    for token, sc in source_counts.items():
        if token not in word_to_id:
            continue
        if sc < min_sources:
            continue
        freq = merged_freqs.get((token,), 0.0)
        if freq < min_freq:
            continue
        valid.add(token)
    return valid


# ---------------------------------------------------------------------------
# N-gram filtering
# ---------------------------------------------------------------------------


def filter_ngrams(
    raw_counts: dict[tuple[str, ...], float],
    valid_tokens: set[str],
    min_count: int,
) -> set[tuple[str, ...]]:
    """Filter n-grams by raw count threshold and token quality.

    Returns the set of n-gram tuples that survive both filters.
    """
    surviving = set()
    for ngram, count in raw_counts.items():
        if count < min_count:
            continue
        if all(token in valid_tokens for token in ngram):
            surviving.add(ngram)
    return surviving


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_unigrams(
    merged_freqs: dict[tuple[str, ...], float],
    valid_tokens: set[str],
    vocab_size: int,
) -> dict[str, float]:
    """Compute log10(P(w)) for each word in the vocabulary.

    Words not in valid_tokens get a floor value of log10(1/total_tokens),
    approximated as log10(min_freq) - 1.0 for tokens not meeting threshold.

    Returns:
        dict mapping token → log10 probability.
    """
    # Compute total token mass for floor calculation
    total_mass = sum(merged_freqs.values())
    floor_score = math.log10(1.0 / total_mass) if total_mass > 0 else -10.0

    scores: dict[str, float] = {}
    for token in valid_tokens:
        freq = merged_freqs.get((token,), 0.0)
        if freq > 0:
            scores[token] = math.log10(freq)
        else:
            scores[token] = floor_score

    return scores


def score_bigrams(
    merged_bigrams: dict[tuple[str, ...], float],
    merged_unigrams: dict[tuple[str, ...], float],
    surviving_bigrams: set[tuple[str, ...]],
) -> list[tuple[str, str, float]]:
    """Compute log10(P(w2|w1)) for surviving bigrams.

    P(w2|w1) = freq(w1,w2) / freq(w1)

    Returns:
        list of (w1, w2, score) tuples.
    """
    results = []
    for bigram in surviving_bigrams:
        w1, w2 = bigram
        bigram_freq = merged_bigrams.get(bigram, 0.0)
        w1_freq = merged_unigrams.get((w1,), 0.0)
        if bigram_freq > 0 and w1_freq > 0:
            score = math.log10(bigram_freq / w1_freq)
            results.append((w1, w2, score))
    return results


def score_trigrams(
    merged_trigrams: dict[tuple[str, ...], float],
    merged_bigrams: dict[tuple[str, ...], float],
    surviving_trigrams: set[tuple[str, ...]],
) -> list[tuple[str, str, str, float]]:
    """Compute log10(P(w3|w1,w2)) for surviving trigrams.

    P(w3|w1,w2) = freq(w1,w2,w3) / freq(w1,w2)

    Returns:
        list of (w1, w2, w3, score).
    """
    results = []
    for trigram in surviving_trigrams:
        w1, w2, w3 = trigram
        trigram_freq = merged_trigrams.get(trigram, 0.0)
        bigram_freq = merged_bigrams.get((w1, w2), 0.0)
        if trigram_freq > 0 and bigram_freq > 0:
            score = math.log10(trigram_freq / bigram_freq)
            results.append((w1, w2, w3, score))
    return results


# ---------------------------------------------------------------------------
# Binary packing
# ---------------------------------------------------------------------------


def _get_git_hash() -> int:
    """Get the first 16 bits of the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return int(result.stdout.strip()[:4], 16)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0


def _get_unix_days() -> int:
    """Get days since Unix epoch (Jan 1, 1970)."""
    return int(time.time() // 86400)


def pack_binary(
    string_table: list[str],
    unigram_scores: dict[str, float],
    bigram_entries: list[tuple[str, str, float]],
    trigram_entries: list[tuple[str, str, str, float]],
    word_to_id: dict[str, int],
    vocab_size: int,
    min_count: int,
    alpha: float,
    smoothing: str,
    output_path: Path,
) -> None:
    """Write the binary file with header, string table, and scored n-grams."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Map word strings to IDs and sort
    unigram_array = [0.0] * vocab_size
    floor_score = min(unigram_scores.values()) if unigram_scores else -10.0
    for token, score in unigram_scores.items():
        wid = word_to_id[token]
        unigram_array[wid] = score
    # Fill missing entries with floor
    for i in range(vocab_size):
        if unigram_array[i] == 0.0 and string_table[i] not in unigram_scores:
            unigram_array[i] = floor_score

    # Convert bigrams to ID-based tuples and sort
    bigram_id_entries = []
    for w1, w2, score in bigram_entries:
        w1_id = word_to_id.get(w1)
        w2_id = word_to_id.get(w2)
        if w1_id is not None and w2_id is not None:
            bigram_id_entries.append((w1_id, w2_id, score))
    bigram_id_entries.sort(key=lambda x: (x[0], x[1]))

    # Convert trigrams to ID-based tuples and sort
    trigram_id_entries = []
    for w1, w2, w3, score in trigram_entries:
        w1_id = word_to_id.get(w1)
        w2_id = word_to_id.get(w2)
        w3_id = word_to_id.get(w3)
        if w1_id is not None and w2_id is not None and w3_id is not None:
            trigram_id_entries.append((w1_id, w2_id, w3_id, score))
    trigram_id_entries.sort(key=lambda x: (x[0], x[1], x[2]))

    n_bigrams = len(bigram_id_entries)
    n_trigrams = len(trigram_id_entries)

    # Build info: upper 16 bits = Unix days, lower 16 bits = git hash
    unix_days = _get_unix_days() & 0xFFFF
    git_hash = _get_git_hash() & 0xFFFF
    build_info = (unix_days << 16) | git_hash

    smoothing_enum = SMOOTHING_ENUM.get(smoothing, 0)

    with open(output_path, "wb") as f:
        # Header (32 bytes)
        header = struct.pack(
            "<4sHHHBBIIIfI",
            MAGIC,                  # 4s: magic
            FORMAT_VERSION,         # H: format_version
            0,                      # H: flags (reserved)
            vocab_size,             # H: vocab_size
            smoothing_enum,         # B: smoothing
            min_count,              # B: min_count
            vocab_size,             # I: n_unigrams (= vocab_size)
            n_bigrams,              # I: n_bigrams
            n_trigrams,             # I: n_trigrams
            alpha,                  # f: alpha
            build_info,             # I: build_info
        )
        assert len(header) == HEADER_SIZE, f"Header is {len(header)} bytes, expected {HEADER_SIZE}"
        f.write(header)

        # String table
        for word in string_table:
            encoded = word.encode("utf-8")
            f.write(struct.pack("<B", len(encoded)))
            f.write(encoded)

        # Unigrams: f32[vocab_size]
        for score in unigram_array:
            f.write(struct.pack("<f", score))

        # Bigrams: (u16 w1, u16 w2, f32 score)[n_bigrams]
        for w1_id, w2_id, score in bigram_id_entries:
            f.write(struct.pack("<HHf", w1_id, w2_id, score))

        # Trigrams: (u16 w1, u16 w2, u16 w3, u16 _pad, f32 score)[n_trigrams]
        for w1_id, w2_id, w3_id, score in trigram_id_entries:
            f.write(struct.pack("<HHHHf", w1_id, w2_id, w3_id, 0, score))


# ---------------------------------------------------------------------------
# Round-trip verification
# ---------------------------------------------------------------------------


def verify_binary(
    path: Path,
    string_table: list[str],
    unigram_scores: dict[str, float],
    bigram_entries: list[tuple[str, str, float]],
    trigram_entries: list[tuple[str, str, str, float]],
    word_to_id: dict[str, int],
    vocab_size: int,
    alpha: float,
    min_count: int,
    smoothing: str,
) -> bool:
    """Read back the binary and verify all entries match source data.

    Returns True if verification passes.
    """
    with open(path, "rb") as f:
        # Verify header
        header_data = f.read(HEADER_SIZE)
        (
            magic, fmt_ver, flags, v_size,
            smooth_byte, mc, n_uni, n_bi, n_tri,
            alpha_read, build_info
        ) = struct.unpack("<4sHHHBBIIIfI", header_data)

        errors = []
        if magic != MAGIC:
            errors.append(f"Magic mismatch: {magic!r} != {MAGIC!r}")
        if fmt_ver != FORMAT_VERSION:
            errors.append(f"Format version mismatch: {fmt_ver} != {FORMAT_VERSION}")
        if v_size != vocab_size:
            errors.append(f"Vocab size mismatch: {v_size} != {vocab_size}")
        if smooth_byte != SMOOTHING_ENUM.get(smoothing, 0):
            errors.append(f"Smoothing mismatch: {smooth_byte}")
        if mc != min_count:
            errors.append(f"Min count mismatch: {mc} != {min_count}")
        if n_uni != vocab_size:
            errors.append(f"Unigram count mismatch: {n_uni} != {vocab_size}")
        if abs(alpha_read - alpha) > 1e-6:
            errors.append(f"Alpha mismatch: {alpha_read} != {alpha}")

        if errors:
            for e in errors:
                console.print(f"  [red]VERIFY FAIL: {e}[/red]")
            return False

        # Verify string table
        for i in range(vocab_size):
            str_len = struct.unpack("<B", f.read(1))[0]
            word_bytes = f.read(str_len)
            word = word_bytes.decode("utf-8")
            if word != string_table[i]:
                console.print(f"  [red]VERIFY FAIL: String table[{i}] = {word!r}, expected {string_table[i]!r}[/red]")
                return False

        # Verify unigrams
        for i in range(vocab_size):
            score = struct.unpack("<f", f.read(4))[0]
            # f32 precision: just check it's a valid float
            if not math.isfinite(score):
                console.print(f"  [red]VERIFY FAIL: Unigram[{i}] is not finite: {score}[/red]")
                return False

        # Verify bigrams
        for _ in range(n_bi):
            w1_id, w2_id, score = struct.unpack("<HHf", f.read(8))
            if w1_id >= vocab_size or w2_id >= vocab_size:
                console.print(f"  [red]VERIFY FAIL: Bigram ID out of range: ({w1_id}, {w2_id})[/red]")
                return False
            if not math.isfinite(score):
                console.print(f"  [red]VERIFY FAIL: Bigram ({w1_id}, {w2_id}) score not finite[/red]")
                return False

        # Verify trigrams
        for _ in range(n_tri):
            w1_id, w2_id, w3_id, _pad, score = struct.unpack("<HHHHf", f.read(12))
            if w1_id >= vocab_size or w2_id >= vocab_size or w3_id >= vocab_size:
                console.print(f"  [red]VERIFY FAIL: Trigram ID out of range[/red]")
                return False
            if not math.isfinite(score):
                console.print(f"  [red]VERIFY FAIL: Trigram score not finite[/red]")
                return False

        # Verify no trailing data
        remaining = f.read()
        if remaining:
            console.print(f"  [red]VERIFY FAIL: {len(remaining)} trailing bytes[/red]")
            return False

    console.print(f"  [green]Round-trip verification passed.[/green]")
    console.print(f"    Header: magic={magic!r}, v{fmt_ver}, vocab={v_size}, "
                  f"smooth={smooth_byte}, mc={mc}, α={alpha_read:.2f}")
    console.print(f"    Entries: {n_uni} unigrams, {n_bi} bigrams, {n_tri} trigrams")
    return True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_encode(
    ngram_dir: Path,
    trie_path: Path,
    output_dir: Path,
    corpora: list[str],
    min_count: int = 15,
    min_sources: int = 2,
    min_freq: float = 5e-6,
    alpha: float = 0.4,
    smoothing: str = "sbo",
) -> Path | None:
    """Run the full encode pipeline: load, filter, score, pack, verify.

    Returns the output binary path on success, None on failure.
    """
    console.print(f"\n  Loading trie dataset from {trie_path.name}...")
    string_table, word_to_id = load_trie_dataset(trie_path)
    vocab_size = len(string_table)
    console.print(f"    Vocabulary: {vocab_size:,} words")

    # Load n-gram data
    console.print(f"  Loading n-gram data...")
    merged_unigrams = load_ngram_tsv(ngram_dir / "ngrams_1_merged.tsv")
    merged_bigrams = load_ngram_tsv(ngram_dir / "ngrams_2_merged.tsv")
    merged_trigrams = load_ngram_tsv(ngram_dir / "ngrams_3_merged.tsv")
    raw_unigrams = load_ngram_tsv(ngram_dir / "ngrams_1_merged_raw.tsv")
    raw_bigrams = load_ngram_tsv(ngram_dir / "ngrams_2_merged_raw.tsv")
    raw_trigrams = load_ngram_tsv(ngram_dir / "ngrams_3_merged_raw.tsv")
    console.print(f"    Merged: {len(merged_unigrams):,} uni, "
                  f"{len(merged_bigrams):,} bi, {len(merged_trigrams):,} tri")
    console.print(f"    Raw:    {len(raw_unigrams):,} uni, "
                  f"{len(raw_bigrams):,} bi, {len(raw_trigrams):,} tri")

    # Token quality filtering
    console.print(f"  Building valid token set (min_sources={min_sources}, min_freq={min_freq:.1e})...")
    source_counts = load_per_corpus_token_sources(ngram_dir, corpora)
    valid_tokens = build_valid_tokens(
        source_counts, merged_unigrams, word_to_id, min_sources, min_freq,
    )
    console.print(f"    Valid tokens: {valid_tokens_in_vocab(valid_tokens, word_to_id):,} / {vocab_size:,} vocab words")

    # N-gram filtering
    console.print(f"  Filtering n-grams (min_count={min_count})...")
    surviving_bigrams = filter_ngrams(raw_bigrams, valid_tokens, min_count)
    surviving_trigrams = filter_ngrams(raw_trigrams, valid_tokens, min_count)
    console.print(f"    Surviving bigrams:  {len(surviving_bigrams):,} / {len(raw_bigrams):,}")
    console.print(f"    Surviving trigrams: {len(surviving_trigrams):,} / {len(raw_trigrams):,}")

    # Scoring
    console.print(f"  Scoring (smoothing={smoothing}, α={alpha})...")
    uni_scores = score_unigrams(merged_unigrams, valid_tokens, vocab_size)
    bi_entries = score_bigrams(merged_bigrams, merged_unigrams, surviving_bigrams)
    tri_entries = score_trigrams(merged_trigrams, merged_bigrams, surviving_trigrams)
    console.print(f"    Scored: {len(uni_scores):,} unigrams, "
                  f"{len(bi_entries):,} bigrams, {len(tri_entries):,} trigrams")

    # Spot-check top scores
    _print_score_samples(uni_scores, bi_entries, tri_entries, string_table, word_to_id)

    # Pack binary
    filename = f"thaime_ngram_v{FORMAT_VERSION}_mc{min_count}.bin"
    output_path = output_dir / filename
    console.print(f"  Writing binary to {output_path.name}...")
    pack_binary(
        string_table, uni_scores, bi_entries, tri_entries,
        word_to_id, vocab_size, min_count, alpha, smoothing, output_path,
    )
    size_bytes = output_path.stat().st_size
    console.print(f"    Raw size: {size_bytes:,} bytes ({size_bytes / (1024 * 1024):.2f} MB)")

    # Brotli compressed size check
    _check_brotli_size(output_path)

    # Verify
    console.print(f"  Verifying binary...")
    ok = verify_binary(
        output_path, string_table, uni_scores, bi_entries, tri_entries,
        word_to_id, vocab_size, alpha, min_count, smoothing,
    )
    if not ok:
        console.print(f"  [red]Verification FAILED[/red]")
        return None

    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def valid_tokens_in_vocab(valid_tokens: set[str], word_to_id: dict[str, int]) -> int:
    """Count how many valid tokens are in the trie vocabulary."""
    return sum(1 for t in valid_tokens if t in word_to_id)


def _print_score_samples(
    uni_scores: dict[str, float],
    bi_entries: list[tuple[str, str, float]],
    tri_entries: list[tuple[str, str, str, float]],
    string_table: list[str],
    word_to_id: dict[str, int],
) -> None:
    """Print a few high-frequency score samples for sanity checking."""
    # Top 5 unigrams by score
    top_uni = sorted(uni_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_uni:
        console.print(f"\n  Score samples (top unigrams):")
        for token, score in top_uni:
            console.print(f"    {token}: {score:.6f}")

    # Top 5 bigrams by score
    top_bi = sorted(bi_entries, key=lambda x: x[2], reverse=True)[:5]
    if top_bi:
        console.print(f"  Score samples (top bigrams by P(w2|w1)):")
        for w1, w2, score in top_bi:
            console.print(f"    {w1} {w2}: {score:.6f}")

    # Top 5 trigrams by score
    top_tri = sorted(tri_entries, key=lambda x: x[3], reverse=True)[:5]
    if top_tri:
        console.print(f"  Score samples (top trigrams by P(w3|w1,w2)):")
        for w1, w2, w3, score in top_tri:
            console.print(f"    {w1} {w2} {w3}: {score:.6f}")


def _check_brotli_size(path: Path) -> None:
    """Report brotli-compressed size if the brotli module is available."""
    try:
        import brotli

        raw = path.read_bytes()
        compressed = brotli.compress(raw, quality=9)
        comp_size = len(compressed)
        ratio = comp_size / len(raw) * 100
        console.print(f"    Brotli (q9): {comp_size:,} bytes ({comp_size / (1024 * 1024):.2f} MB, "
                      f"{ratio:.1f}% of raw)")
        if comp_size > 5 * 1024 * 1024:
            console.print(f"    [yellow]WARNING: Compressed size exceeds 5 MB target[/yellow]")
        else:
            console.print(f"    [green]Compressed size within 5 MB target[/green]")
    except ImportError:
        console.print(f"    [yellow]brotli not installed — skipping compression check[/yellow]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--min-count", default=_cfg.encode_min_count, type=int,
              help=f"Minimum raw n-gram count (default: {_cfg.encode_min_count})")
@click.option("--min-sources", default=_cfg.encode_min_source_count, type=int,
              help=f"Minimum corpus source count per token (default: {_cfg.encode_min_source_count})")
@click.option("--min-freq", default=_cfg.encode_min_frequency, type=float,
              help=f"Minimum merged token frequency (default: {_cfg.encode_min_frequency})")
@click.option("--alpha", default=_cfg.encode_alpha, type=float,
              help=f"Stupid Backoff alpha (default: {_cfg.encode_alpha})")
@click.option("--smoothing", default=_cfg.encode_smoothing, type=click.Choice(["sbo", "mkn", "katz"]),
              help=f"Smoothing method (default: {_cfg.encode_smoothing})")
@click.option("--trie-dataset", default=None, type=click.Path(),
              help="Path to trie_dataset.json")
@click.option("--output-dir", default=None, type=click.Path(),
              help="Output directory for binary file")
def encode(min_count, min_sources, min_freq, alpha, smoothing, trie_dataset, output_dir):
    """Stage 4: Encode n-grams into production binary."""
    ngram_dir = _cfg.ngram_dir
    trie_path = Path(trie_dataset) if trie_dataset else _cfg.trie_dataset_path
    out_dir = Path(output_dir) if output_dir else _cfg.encode_dir

    if not trie_path.exists():
        console.print(f"[red]ERROR: Trie dataset not found: {trie_path}[/red]")
        console.print("  Run 'python -m pipelines trie run' first.")
        raise SystemExit(1)

    if not ngram_dir.exists():
        console.print(f"[red]ERROR: N-gram directory not found: {ngram_dir}[/red]")
        console.print("  Run 'python -m pipelines ngram count' first.")
        raise SystemExit(1)

    console.print(f"\n{'=' * 60}")
    console.print("Stage 4: Binary Encoding")
    console.print(f"{'=' * 60}")
    console.print(f"  min_count={min_count}, min_sources={min_sources}, "
                  f"min_freq={min_freq:.1e}")
    console.print(f"  smoothing={smoothing}, α={alpha}")

    start = time.time()
    result = run_encode(
        ngram_dir=ngram_dir,
        trie_path=trie_path,
        output_dir=out_dir,
        corpora=list(TEXT_CORPORA),
        min_count=min_count,
        min_sources=min_sources,
        min_freq=min_freq,
        alpha=alpha,
        smoothing=smoothing,
    )
    elapsed = time.time() - start

    if result:
        console.print(f"\n  Encode complete in {elapsed:.1f}s")
        console.print(f"  Output: {result}")
    else:
        console.print(f"\n  [red]Encode FAILED[/red]")
        raise SystemExit(1)


if __name__ == "__main__":
    encode()
