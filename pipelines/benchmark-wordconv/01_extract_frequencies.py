"""Step 1: Extract word frequencies from Thai NLP corpora.

Tokenizes the three selected corpora (wisesight, wongnai, prachathai),
computes per-corpus word frequencies, normalizes them, then produces a
weighted-average merged frequency list.

Output: pipelines/benchmark-wordconv/output/word_frequencies.csv

Usage:
    python -m pipelines.benchmark-wordconv.01_extract_frequencies
    python -m pipelines.benchmark-wordconv.01_extract_frequencies --top-k 500
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from pythainlp.tokenize import word_tokenize

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = REPO_ROOT / "data" / "corpora" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ---------------------------------------------------------------------------
# Corpus readers
# ---------------------------------------------------------------------------

# Regex: matches strings that are purely Thai script (no spaces, digits, etc.)
_THAI_WORD_RE = re.compile(r"^[\u0e01-\u0e3a\u0e40-\u0e4e\u0e50-\u0e59]+$")

# Skip very short or long words
_MIN_WORD_LEN = 2  # at least 2 Thai characters
_MAX_WORD_LEN = 30


def _is_valid_thai_word(token: str) -> bool:
    """Check if a token is a valid Thai word for our purposes."""
    if not token or len(token) < _MIN_WORD_LEN or len(token) > _MAX_WORD_LEN:
        return False
    return bool(_THAI_WORD_RE.match(token))


def _tokenize_text(text: str) -> list[str]:
    """Tokenize Thai text and filter to valid Thai words."""
    tokens = word_tokenize(text, engine="newmm")
    return [t for t in tokens if _is_valid_thai_word(t)]


def read_wisesight() -> Counter:
    """Read Wisesight corpus and return word frequencies."""
    wisesight_dir = RAW_DATA_DIR / "wisesight"
    counter: Counter = Counter()
    files = ["pos.txt", "neg.txt", "neu.txt", "q.txt"]

    for fname in files:
        fpath = wisesight_dir / fname
        if not fpath.exists():
            print(f"  WARNING: {fpath} not found, skipping")
            continue
        print(f"  Reading {fpath.name}...")
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        line_iter = enumerate(lines)
        if tqdm is not None:
            line_iter = tqdm(list(line_iter), desc=f"    {fname}", unit="line", leave=False)
        for i, line in line_iter:
            line = line.strip()
            if line:
                counter.update(_tokenize_text(line))
            if tqdm is None and (i + 1) % 5000 == 0:
                print(f"    Processed {i + 1} lines...")

    return counter


def read_wongnai() -> Counter:
    """Read Wongnai corpus and return word frequencies."""
    wongnai_file = RAW_DATA_DIR / "wongnai" / "w_review_train.csv"
    counter: Counter = Counter()

    if not wongnai_file.exists():
        print(f"  WARNING: {wongnai_file} not found, skipping")
        return counter

    print(f"  Reading {wongnai_file.name}...")
    with open(wongnai_file, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f, delimiter=";"))
    row_iter = enumerate(reader)
    if tqdm is not None:
        row_iter = tqdm(list(row_iter), desc="    wongnai", unit="row", leave=False)
    for i, row in row_iter:
        if i == 0:
            continue  # skip header
        if len(row) >= 1:
            text = row[0]
            counter.update(_tokenize_text(text))
        if tqdm is None and (i + 1) % 50000 == 0:
            print(f"    Processed {i + 1} rows...")

    return counter


def read_prachathai() -> Counter:
    """Read Prachathai corpus and return word frequencies."""
    prachathai_dir = RAW_DATA_DIR / "prachathai" / "data"
    counter: Counter = Counter()
    files = ["train.jsonl", "valid.jsonl", "test.jsonl"]

    for fname in files:
        fpath = prachathai_dir / fname
        if not fpath.exists():
            print(f"  WARNING: {fpath} not found, skipping")
            continue
        print(f"  Reading {fpath.name}...")
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        line_iter = enumerate(lines)
        if tqdm is not None:
            line_iter = tqdm(list(line_iter), desc=f"    {fname}", unit="line", leave=False)
        for i, line in line_iter:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Tokenize both title and body
                for field in ["title", "body_text"]:
                    text = data.get(field, "")
                    if text:
                        counter.update(_tokenize_text(text))
            except json.JSONDecodeError:
                continue
            if tqdm is None and (i + 1) % 10000 == 0:
                print(f"    Processed {i + 1} articles...")

    return counter


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def normalize_frequencies(counter: Counter) -> dict[str, float]:
    """Normalize frequency counts to sum to 1.0."""
    total = sum(counter.values())
    if total == 0:
        return {}
    return {word: count / total for word, count in counter.items()}


def merge_frequencies(
    freq_dicts: list[dict[str, float]],
    weights: list[float] | None = None,
) -> dict[str, float]:
    """Merge multiple normalized frequency dicts with weighted averaging.

    Args:
        freq_dicts: List of {word: normalized_freq} dicts.
        weights: Weights for each dict (default: equal weights).

    Returns:
        Merged {word: weighted_avg_freq} dict.
    """
    if weights is None:
        weights = [1.0 / len(freq_dicts)] * len(freq_dicts)
    else:
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

    merged: dict[str, float] = {}
    all_words = set()
    for fd in freq_dicts:
        all_words.update(fd.keys())

    for word in all_words:
        score = 0.0
        for fd, w in zip(freq_dicts, weights):
            score += fd.get(word, 0.0) * w
        merged[word] = score

    return merged


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract word frequencies from Thai NLP corpora."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=500,
        help="Number of top words to output (default: 500)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: output/word_frequencies.csv)",
    )
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else OUTPUT_DIR / "word_frequencies.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Read each corpus
    print("=" * 60)
    print("Step 1: Reading corpora")
    print("=" * 60)

    print("\n[1/3] Wisesight Sentiment Corpus (informal social media)")
    wisesight_freq = read_wisesight()
    print(f"  → {len(wisesight_freq)} unique words, {sum(wisesight_freq.values()):,} total tokens")

    print("\n[2/3] Wongnai Reviews (informal reviews)")
    wongnai_freq = read_wongnai()
    print(f"  → {len(wongnai_freq)} unique words, {sum(wongnai_freq.values()):,} total tokens")

    print("\n[3/3] Prachathai 67K (formal news)")
    prachathai_freq = read_prachathai()
    print(f"  → {len(prachathai_freq)} unique words, {sum(prachathai_freq.values()):,} total tokens")

    # Step 2: Normalize and merge with equal weights
    print("\n" + "=" * 60)
    print("Step 2: Normalizing and merging (equal weight per corpus)")
    print("=" * 60)

    norm_wisesight = normalize_frequencies(wisesight_freq)
    norm_wongnai = normalize_frequencies(wongnai_freq)
    norm_prachathai = normalize_frequencies(prachathai_freq)

    merged = merge_frequencies(
        [norm_wisesight, norm_wongnai, norm_prachathai],
        weights=[1.0, 1.0, 1.0],  # equal weights
    )

    print(f"  Total unique words across all corpora: {len(merged):,}")

    # Step 3: Rank and output top-k
    print(f"\n  Selecting top {args.top_k} words by weighted frequency...")

    # Use Counter.most_common(k) for O(n log k) top-k selection
    # instead of a full O(n log n) sort of the entire vocabulary.
    merged_counter = Counter(merged)
    top_k = merged_counter.most_common(args.top_k)

    # Lazy per-corpus ranks: only compute ranks for the top-k words,
    # not the entire vocabulary. For each top-k word, its per-corpus
    # rank is 1 + the count of corpus words with strictly higher frequency.
    top_k_words = {word for word, _ in top_k}

    def _lazy_ranks(
        norm_freq: dict[str, float], top_words: set[str]
    ) -> dict[str, int]:
        """Compute per-corpus ranks only for the requested words.

        For each word in top_words that exists in norm_freq, rank is
        1 + number of words in the corpus with strictly higher frequency.
        This avoids sorting the entire corpus vocabulary.
        """
        # Filter to only the top-k words present in this corpus
        relevant = {
            w: freq for w, freq in norm_freq.items() if w in top_words
        }
        if not relevant:
            return {}
        # Sort only the relevant subset
        sorted_words = sorted(relevant.items(), key=lambda x: x[1], reverse=True)
        return {w: i + 1 for i, (w, _) in enumerate(sorted_words)}

    wisesight_rank = _lazy_ranks(norm_wisesight, top_k_words)
    wongnai_rank = _lazy_ranks(norm_wongnai, top_k_words)
    prachathai_rank = _lazy_ranks(norm_prachathai, top_k_words)

    # Write output
    print(f"\n  Writing to {output_path}")
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rank",
            "thai_word",
            "merged_freq",
            "wisesight_rank",
            "wongnai_rank",
            "prachathai_rank",
            "corpus_count",
        ])
        for i, (word, freq) in enumerate(top_k):
            ws_r = wisesight_rank.get(word, "")
            wn_r = wongnai_rank.get(word, "")
            pt_r = prachathai_rank.get(word, "")
            corpus_count = sum(1 for r in [ws_r, wn_r, pt_r] if r != "")
            writer.writerow([
                i + 1,
                word,
                f"{freq:.10f}",
                ws_r,
                wn_r,
                pt_r,
                corpus_count,
            ])

    print(f"\n  Done! Top 10 words:")
    for i, (word, freq) in enumerate(top_k[:10]):
        print(f"    {i + 1:3d}. {word}  (freq: {freq:.8f})")

    print(f"\n  Output: {output_path}")
    print(f"  Total entries: {len(top_k)}")


if __name__ == "__main__":
    main()
