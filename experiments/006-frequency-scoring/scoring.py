"""
Scoring Formulas for Frequency-Based Candidate Ranking

Implements 6 pluggable cost functions for the THAIME Viterbi candidate
selection algorithm. Each formula maps (word_id, word_data) → cost (float),
where lower cost = better candidate.

Usage:
    from scoring import SCORING_FORMULAS, load_trie_dataset

    dataset = load_trie_dataset("reference/trie_dataset_sample_5k.json")
    word_data = dataset["word_data"]  # word_id → enriched dict
    cost = SCORING_FORMULAS["baseline"](word_id=0, word_data=word_data[0])

Author: THAIME Research
Date: 2025-07-14
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# Minimum frequency floor to prevent -inf from log(0)
MIN_FREQ: float = 1e-7


# ---------------------------------------------------------------------------
# Formula 1: Current baseline — raw frequency
# ---------------------------------------------------------------------------

def formula_baseline_cost(word_id: int, word_data: dict, **params) -> float:
    """cost = -log(freq_avg)

    Direct negative log-likelihood of the pre-normalised corpus frequency.
    This mirrors the current R005 edge_cost function.
    """
    freq = max(word_data["frequency"], MIN_FREQ)
    return -math.log(freq)


# ---------------------------------------------------------------------------
# Formula 2: Source-count weighted frequency
# ---------------------------------------------------------------------------

def formula_source_weighted_cost(word_id: int, word_data: dict, **params) -> float:
    """cost = -log(freq_avg) - alpha * log(source_count / total_sources)

    Words appearing in more corpora receive a bonus (lower cost).
    """
    alpha: float = params.get("alpha", 1.0)
    total_sources: int = params.get("total_sources", 5)

    freq = max(word_data["frequency"], MIN_FREQ)
    source_count = max(word_data["source_count"], 1)

    cost = -math.log(freq) - alpha * math.log(source_count / total_sources)
    return cost


# ---------------------------------------------------------------------------
# Formula 3: TF-IDF inspired (negative control)
# ---------------------------------------------------------------------------

def formula_tfidf_cost(word_id: int, word_data: dict, **params) -> float:
    """cost = -log(freq_avg * idf)  where idf = log(total_sources / source_count)

    Negative control — up-weights rare-source words, expected to HURT
    performance on common-word tasks.
    """
    total_sources: int = params.get("total_sources", 5)

    freq = max(word_data["frequency"], MIN_FREQ)
    source_count = max(word_data["source_count"], 1)

    if source_count >= total_sources:
        # Edge case: word in all corpora → idf would be log(1)=0
        idf = math.log(total_sources / (source_count - 0.5))
    else:
        idf = math.log(total_sources / source_count)

    product = freq * idf
    product = max(product, MIN_FREQ)
    return -math.log(product)


# ---------------------------------------------------------------------------
# Formula 4: Rank-based scoring
# ---------------------------------------------------------------------------

def formula_rank_cost(word_id: int, word_data: dict, **params) -> float:
    """cost = log(rank)

    Pure rank-based scoring that ignores absolute frequency values.
    rank is 1-based (most frequent word = rank 1).
    """
    rank = max(word_data["rank"], 1)
    return math.log(rank)


# ---------------------------------------------------------------------------
# Formula 5: Log-smoothed frequency with source bonus
# ---------------------------------------------------------------------------

def formula_smoothed_cost(word_id: int, word_data: dict, **params) -> float:
    """cost = -log((freq_avg + delta) / (1 + delta * vocab_size)) - beta * log(source_count)

    Additive smoothing prevents zero-frequency blow-up;
    source-count bonus is scaled by beta.
    """
    delta: float = params.get("delta", 1e-6)
    beta: float = params.get("beta", 0.5)
    vocab_size: int = params.get("vocab_size", 5000)

    freq = word_data["frequency"]
    source_count = max(word_data["source_count"], 1)

    smoothed = (freq + delta) / (1.0 + delta * vocab_size)
    smoothed = max(smoothed, MIN_FREQ)
    cost = -math.log(smoothed) - beta * math.log(source_count)
    return cost


# ---------------------------------------------------------------------------
# Formula 6: Corpus-balanced frequency
# ---------------------------------------------------------------------------

def formula_balanced_cost(word_id: int, word_data: dict, **params) -> float:
    """Corpus-balanced frequency scoring.

    freq_balanced = mean(freq_c / max_freq_c) over corpora where word is present
    cost = -log(freq_balanced)

    Falls back to Formula 1 (baseline) when per-corpus data is unavailable.
    """
    per_corpus = word_data.get("per_corpus_frequencies", {})
    max_corpus_freqs: dict = params.get("max_corpus_freqs", {})

    if not per_corpus or not max_corpus_freqs:
        # Fallback to baseline
        return formula_baseline_cost(word_id, word_data)

    ratios = []
    for corpus, freq_c in per_corpus.items():
        max_freq_c = max_corpus_freqs.get(corpus, 1.0)
        if max_freq_c > 0:
            ratios.append(freq_c / max_freq_c)

    if not ratios:
        return formula_baseline_cost(word_id, word_data)

    freq_balanced = sum(ratios) / len(ratios)
    freq_balanced = max(freq_balanced, MIN_FREQ)
    return -math.log(freq_balanced)


# ---------------------------------------------------------------------------
# Formula registry
# ---------------------------------------------------------------------------

SCORING_FORMULAS: dict[str, callable] = {
    "baseline": formula_baseline_cost,
    "source_weighted": formula_source_weighted_cost,
    "tfidf": formula_tfidf_cost,
    "rank": formula_rank_cost,
    "smoothed": formula_smoothed_cost,
    "balanced": formula_balanced_cost,
}


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def prepare_word_data(
    trie_dataset: dict,
    per_corpus_path: str | Path | None = None,
) -> dict[int, dict]:
    """Enrich trie dataset entries with derived fields for scoring.

    Adds:
        source_count (int): number of corpora the word appears in
        rank (int): 1-based frequency rank (1 = most frequent)
        per_corpus_frequencies (dict): per-corpus normalized frequencies
            (loaded from per_corpus_path if provided)

    Returns:
        Mapping word_id → enriched word data dict.
    """
    entries = trie_dataset["entries"]

    # Sort by frequency descending to assign ranks
    sorted_entries = sorted(entries, key=lambda e: e["frequency"], reverse=True)
    rank_map: dict[int, int] = {}
    for rank_1based, entry in enumerate(sorted_entries, start=1):
        rank_map[entry["word_id"]] = rank_1based

    # Load per-corpus frequencies if available
    per_corpus_data: dict[str, dict] = {}
    max_corpus_freqs: dict[str, float] = {}
    if per_corpus_path is not None:
        per_corpus_path = Path(per_corpus_path)
        if per_corpus_path.exists():
            with open(per_corpus_path, encoding="utf-8") as f:
                pc_raw = json.load(f)
            per_corpus_data = pc_raw.get("per_word", {})
            # Compute max frequency per corpus from the data
            for wid_str, freqs in per_corpus_data.items():
                for corpus, freq_val in freqs.items():
                    if corpus not in max_corpus_freqs or freq_val > max_corpus_freqs[corpus]:
                        max_corpus_freqs[corpus] = freq_val

    word_data: dict[int, dict] = {}
    for entry in entries:
        wid = entry["word_id"]
        pc_freqs = per_corpus_data.get(str(wid), {})
        word_data[wid] = {
            "word_id": wid,
            "thai": entry["thai"],
            "frequency": entry["frequency"],
            "sources": entry["sources"],
            "source_count": len(entry["sources"]),
            "rank": rank_map[wid],
            "romanizations": entry["romanizations"],
            "per_corpus_frequencies": pc_freqs,
        }

    return word_data, max_corpus_freqs


def load_trie_dataset(
    path: str | Path,
    per_corpus_path: str | Path | None = None,
) -> dict:
    """Load the trie dataset JSON and prepare enriched word data.

    Args:
        path: Path to trie_dataset_sample_5k.json
        per_corpus_path: Optional path to per_corpus_frequencies.json

    Returns:
        Dict with keys:
            "raw": the original parsed JSON
            "word_data": word_id → enriched dict (from prepare_word_data)
            "metadata": dataset metadata
            "max_corpus_freqs": max frequency per corpus (for balanced formula)
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    word_data, max_corpus_freqs = prepare_word_data(raw, per_corpus_path)
    return {
        "raw": raw,
        "word_data": word_data,
        "metadata": raw["metadata"],
        "max_corpus_freqs": max_corpus_freqs,
    }
