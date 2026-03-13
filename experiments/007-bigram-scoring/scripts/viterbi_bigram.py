"""Phase 4: Bigram-aware Viterbi prototype with real trie data.

Integrates Stupid Backoff bigram scoring into the Viterbi candidate selection
algorithm (originally prototyped in Research 005 with unigram-only scoring).

Usage:
    # Default: sweep bigram_weight on all row types
    python -m experiments.007-bigram-scoring.scripts.viterbi_bigram

    # Verbose with specific weights
    python -m experiments.007-bigram-scoring.scripts.viterbi_bigram --bigram-weights 0.0,1.0 --verbose

    # Specific row types
    python -m experiments.007-bigram-scoring.scripts.viterbi_bigram --types bigram
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .config import OUTPUT_DIR, TRIE_DATASET_PATH
from .evaluate_smoothing import (
    BigramStats,
    load_benchmark,
    load_bigram_counts,
    score_stupid_backoff,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "benchmarks" / "ranking" / "bigram" / "v0.1.1.csv"
)
RAW_MERGED_PATH = OUTPUT_DIR / "ngrams_2_merged_raw.tsv"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WordEntry:
    """A word from the trie dataset."""
    word_id: int
    thai: str
    frequency: float
    romanization: str  # The specific romanization key that matched


@dataclass
class LatticeEdge:
    """A single edge in the word lattice."""
    start: int          # Start position in the Latin input string
    end: int            # End position (exclusive)
    word_id: int
    thai_text: str
    frequency: float
    romanization: str   # The Latin substring that matched


@dataclass
class ScoredPath:
    """A complete path through the lattice with its score."""
    edges: list[LatticeEdge]
    score: float
    thai_text: str = ""

    def __post_init__(self):
        if not self.thai_text and self.edges:
            self.thai_text = "".join(e.thai_text for e in self.edges)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

# Minimum frequency floor to prevent -inf for zero-frequency words
MIN_FREQUENCY = 1e-7


def load_trie_dataset(path: Path) -> list[dict]:
    """Load trie_dataset.json and return the entries list."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["entries"]


def build_romanization_index(entries: list[dict]) -> dict[str, list[WordEntry]]:
    """Build romanization key -> list[WordEntry] mapping.

    Each word may have multiple romanization keys; each key maps to
    all words that share that romanization (collision set).
    """
    index: dict[str, list[WordEntry]] = {}
    for entry in entries:
        for rom in entry["romanizations"]:
            we = WordEntry(
                word_id=entry["word_id"],
                thai=entry["thai"],
                frequency=entry["frequency"],
                romanization=rom,
            )
            if rom not in index:
                index[rom] = []
            index[rom].append(we)
    return index


# ---------------------------------------------------------------------------
# Lattice construction
# ---------------------------------------------------------------------------

def build_lattice(
    latin_input: str,
    rom_index: dict[str, list[WordEntry]],
) -> list[LatticeEdge]:
    """Build a word lattice via substring matching on the input string.

    For each position i, try all substrings input[i:j] and look up in
    the romanization index. O(L²) in input length.
    """
    edges: list[LatticeEdge] = []
    input_len = len(latin_input)

    for start in range(input_len):
        for end in range(start + 1, input_len + 1):
            substring = latin_input[start:end]
            if substring in rom_index:
                for we in rom_index[substring]:
                    edges.append(LatticeEdge(
                        start=start,
                        end=end,
                        word_id=we.word_id,
                        thai_text=we.thai,
                        frequency=we.frequency,
                        romanization=substring,
                    ))

    return edges


# ---------------------------------------------------------------------------
# Bigram-aware Viterbi
# ---------------------------------------------------------------------------

def viterbi_bigram(
    latin_input: str,
    lattice: list[LatticeEdge],
    stats: BigramStats,
    alpha: float = 0.4,
    bigram_weight: float = 1.0,
    segmentation_penalty: float = 0.5,
    context_word: str = "<BOS>",
    k: int = 10,
) -> list[ScoredPath]:
    """Find top-k paths using bigram-aware Viterbi.

    State: (position, prev_thai_text) — expands the state space to track
    the previous word for bigram scoring.

    Edge cost = unigram_cost + bigram_weight * bigram_cost + segmentation_penalty

    When prev_word is <BOS> or unseen, bigram_cost is 0 (pure unigram fallback).

    Args:
        latin_input: The Latin input string
        lattice: List of lattice edges from build_lattice()
        stats: Precomputed bigram statistics
        alpha: Stupid Backoff alpha parameter
        bigram_weight: Weight for bigram cost component (0 = unigram only)
        segmentation_penalty: Per-word penalty
        context_word: Previous Thai word for context seeding
        k: Number of top candidates to return

    Returns:
        List of ScoredPath objects, sorted by score (best first).
    """
    input_len = len(latin_input)

    # Group edges by start position
    edges_from: dict[int, list[LatticeEdge]] = {}
    for edge in lattice:
        if edge.start not in edges_from:
            edges_from[edge.start] = []
        edges_from[edge.start].append(edge)

    # State: best_paths_at[(pos, prev_thai)] = list of (score, edge_list)
    # Initial state: position 0, previous word is the context
    best_paths_at: dict[tuple[int, str], list[tuple[float, list[LatticeEdge]]]] = {
        (0, context_word): [(0.0, [])],
    }

    # Process positions left to right
    for pos in range(input_len):
        if pos not in edges_from:
            continue

        # Collect all states at this position
        states_at_pos = [
            (prev_word, entries)
            for (p, prev_word), entries in best_paths_at.items()
            if p == pos
        ]

        if not states_at_pos:
            continue

        for edge in edges_from[pos]:
            # Unigram cost
            freq = max(edge.frequency, MIN_FREQUENCY)
            unigram_cost = -math.log(freq)

            for prev_word, prev_entries in states_at_pos:
                # Bigram cost
                if bigram_weight > 0 and prev_word != "<BOS>":
                    bigram_cost = score_stupid_backoff(
                        stats, prev_word, edge.thai_text, alpha=alpha
                    )
                else:
                    bigram_cost = 0.0

                edge_cost = (
                    unigram_cost
                    + bigram_weight * bigram_cost
                    + segmentation_penalty
                )

                for prev_score, prev_path in prev_entries:
                    new_score = prev_score + edge_cost
                    new_path = prev_path + [edge]

                    key = (edge.end, edge.thai_text)
                    if key not in best_paths_at:
                        best_paths_at[key] = []

                    best_paths_at[key].append((new_score, new_path))

                    # k-best pruning per state
                    if len(best_paths_at[key]) > k:
                        best_paths_at[key].sort(key=lambda x: x[0])
                        best_paths_at[key] = best_paths_at[key][:k]

    # Extract complete paths at final position
    final_entries: list[tuple[float, list[LatticeEdge]]] = []
    for (pos, prev_word), entries in best_paths_at.items():
        if pos == input_len:
            final_entries.extend(entries)

    if not final_entries:
        return []

    # Sort, deduplicate by thai_text, return top-k
    final_entries.sort(key=lambda x: x[0])

    results: list[ScoredPath] = []
    seen_texts: set[str] = set()
    for score, path in final_entries:
        sp = ScoredPath(edges=path, score=score)
        if sp.thai_text not in seen_texts:
            seen_texts.add(sp.thai_text)
            results.append(sp)
            if len(results) >= k:
                break

    return results


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(
    benchmark_rows: list[dict],
    rom_index: dict[str, list[WordEntry]],
    stats: BigramStats,
    bigram_weight: float,
    alpha: float = 0.4,
    segmentation_penalty: float = 0.5,
    k: int = 10,
    verbose: bool = False,
) -> dict:
    """Evaluate bigram Viterbi on benchmark rows.

    For each row:
      1. Build lattice from latin_input
      2. Run Viterbi with context_word
      3. Find rank of expected_top in output paths
    """
    ranks = []
    details = []

    for row in benchmark_rows:
        context = row.get("context", "")
        expected = row["expected_top"]
        latin = row["latin_input"]
        row_type = row.get("type", "unknown")

        # Build lattice
        lattice = build_lattice(latin, rom_index)
        if not lattice:
            if verbose:
                print(f"  NO LATTICE: {latin} (no romanization matches)")
            continue

        # Run Viterbi
        context_word = context if context else "<BOS>"
        paths = viterbi_bigram(
            latin, lattice, stats,
            alpha=alpha,
            bigram_weight=bigram_weight,
            segmentation_penalty=segmentation_penalty,
            context_word=context_word,
            k=k,
        )

        if not paths:
            if verbose:
                print(f"  NO PATHS: {latin} (lattice has {len(lattice)} edges but no valid paths)")
            continue

        # Find rank of expected (1-indexed)
        rank = None
        for i, p in enumerate(paths):
            if p.thai_text == expected:
                rank = i + 1
                break

        if rank is None:
            # Expected not in top-k; assign rank = k+1
            rank = len(paths) + 1

        ranks.append(rank)

        detail = {
            "context": context,
            "expected": expected,
            "latin": latin,
            "type": row_type,
            "rank": rank,
            "top_candidate": paths[0].thai_text if paths else "",
            "top_score": paths[0].score if paths else float("inf"),
            "n_candidates": len(paths),
            "n_lattice_edges": len(lattice),
        }
        details.append(detail)

        if verbose and rank > 1:
            top3 = ", ".join(f"{p.thai_text}({p.score:.3f})" for p in paths[:3])
            print(f"  MISS rank={rank}: {context}+{latin} -> expect {expected}, "
                  f"got [{top3}]")

    # Compute metrics
    n = len(ranks)
    if n == 0:
        return {"mrr": 0.0, "top1_acc": 0.0, "n": 0, "details": details}

    mrr = sum(1.0 / r for r in ranks) / n
    top1_acc = sum(1 for r in ranks if r == 1) / n

    return {
        "mrr": mrr,
        "top1_acc": top1_acc,
        "n": n,
        "details": details,
        "rank_distribution": Counter(ranks),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 4: Bigram-aware Viterbi prototype evaluation."
    )
    parser.add_argument(
        "--bigram-weights",
        type=str,
        default="0.0,0.5,1.0,1.5,2.0",
        help="Comma-separated bigram_weight values to sweep (default: 0.0,0.5,1.0,1.5,2.0)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-row miss details",
    )
    parser.add_argument(
        "--types",
        type=str,
        default="all",
        help="Benchmark row types to evaluate: bigram,compound,baseline,all (default: all)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.4,
        help="Stupid Backoff alpha (default: 0.4)",
    )
    parser.add_argument(
        "--segmentation-penalty",
        type=float,
        default=0.5,
        help="Per-word segmentation penalty (default: 0.5)",
    )
    args = parser.parse_args()

    bigram_weights = [float(w) for w in args.bigram_weights.split(",")]

    # ---- Load data ----
    print("Loading data...")

    if not TRIE_DATASET_PATH.exists():
        print(f"ERROR: Trie dataset not found: {TRIE_DATASET_PATH}")
        sys.exit(1)

    trie_entries = load_trie_dataset(TRIE_DATASET_PATH)
    print(f"  Trie entries: {len(trie_entries):,} words")

    rom_index = build_romanization_index(trie_entries)
    print(f"  Romanization keys: {len(rom_index):,}")

    if not RAW_MERGED_PATH.exists():
        print(f"ERROR: Raw merged bigrams not found: {RAW_MERGED_PATH}")
        print("  Run count_ngrams.py first (Stage 2).")
        sys.exit(1)

    bigram_counts = load_bigram_counts(RAW_MERGED_PATH)
    print(f"  Bigram counts: {len(bigram_counts):,} entries")

    stats = BigramStats(bigram_counts)
    print(f"  Vocab size: {stats.vocab_size:,}")

    benchmark = load_benchmark(BENCHMARK_PATH)
    print(f"  Benchmark rows: {len(benchmark)}")

    # Filter by type
    eval_types = args.types.split(",")
    if "all" in eval_types:
        eval_rows = benchmark
    else:
        eval_rows = [r for r in benchmark if r.get("type") in eval_types]

    # Group by type for per-type breakdown
    rows_by_type: dict[str, list[dict]] = {}
    for row in eval_rows:
        t = row.get("type", "unknown")
        if t not in rows_by_type:
            rows_by_type[t] = []
        rows_by_type[t].append(row)

    type_counts = ", ".join(f"{t}:{len(rs)}" for t, rs in sorted(rows_by_type.items()))
    print(f"  Evaluating: {len(eval_rows)} rows ({type_counts})")

    # ---- Parameter sweep ----
    print(f"\nFixed params: alpha={args.alpha}, seg_penalty={args.segmentation_penalty}")
    print(f"Sweeping bigram_weight: {bigram_weights}")

    # Store results for summary table
    all_results: list[tuple[float, dict, dict[str, dict]]] = []

    for bw in bigram_weights:
        print(f"\n{'=' * 74}")
        print(f"bigram_weight = {bw}")
        print(f"{'=' * 74}")

        # Overall evaluation
        result = evaluate(
            eval_rows, rom_index, stats,
            bigram_weight=bw,
            alpha=args.alpha,
            segmentation_penalty=args.segmentation_penalty,
            verbose=args.verbose,
        )

        print(f"\n  Overall: MRR={result['mrr']:.4f}, "
              f"Top-1={result['top1_acc']:.1%} ({int(result['top1_acc'] * result['n'])}/{result['n']})")

        if result.get("rank_distribution"):
            dist = result["rank_distribution"]
            dist_str = ", ".join(f"r{k}:{v}" for k, v in sorted(dist.items())[:5])
            print(f"  Rank dist: {dist_str}")

        # Per-type breakdown
        type_results: dict[str, dict] = {}
        for row_type, rows in sorted(rows_by_type.items()):
            tr = evaluate(
                rows, rom_index, stats,
                bigram_weight=bw,
                alpha=args.alpha,
                segmentation_penalty=args.segmentation_penalty,
            )
            type_results[row_type] = tr
            print(f"  {row_type:>10}: MRR={tr['mrr']:.4f}, "
                  f"Top-1={tr['top1_acc']:.1%} ({int(tr['top1_acc'] * tr['n'])}/{tr['n']})")

        all_results.append((bw, result, type_results))

    # ---- Summary table ----
    print(f"\n{'=' * 74}")
    print("SUMMARY")
    print(f"{'=' * 74}")

    # Header
    type_names = sorted(rows_by_type.keys())
    header_parts = [f"{'bw':>5}", f"{'MRR':>7}", f"{'Top-1':>7}"]
    for t in type_names:
        header_parts.append(f"{t[:8]:>9}")
    print("  " + " ".join(header_parts))
    print("  " + " ".join(["-" * 5, "-" * 7, "-" * 7] + ["-" * 9] * len(type_names)))

    for bw, result, type_results in all_results:
        parts = [f"{bw:>5.1f}", f"{result['mrr']:>7.4f}", f"{result['top1_acc']:>6.1%}"]
        for t in type_names:
            tr = type_results.get(t, {"mrr": 0.0})
            parts.append(f"{tr['mrr']:>9.4f}")
        print("  " + " ".join(parts))

    print()


if __name__ == "__main__":
    main()
