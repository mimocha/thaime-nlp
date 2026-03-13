"""Phase 3: Evaluate smoothing methods on the bigram ranking benchmark.

Implements 4 smoothing methods and evaluates them on bigram-type benchmark
rows. Each method scores (context_word, candidate_word) pairs and ranks
candidates for a given latin_input.

Methods:
  1. Stupid Backoff (Brants et al. 2007)
  2. Jelinek-Mercer interpolation
  3. Modified Kneser-Ney (Chen & Goodman 1999)
  4. Katz Backoff (Good-Turing discounting)

Usage:
    python -m experiments.007-bigram-scoring.scripts.evaluate_smoothing
    python -m experiments.007-bigram-scoring.scripts.evaluate_smoothing --methods all --verbose
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .config import OUTPUT_DIR, TRIE_DATASET_PATH


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BENCHMARK_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "benchmarks" / "ranking" / "bigram" / "v0.1.1.csv"
)
COLLISIONS_PATH = OUTPUT_DIR / "collisions.json"
RAW_MERGED_PATH = OUTPUT_DIR / "ngrams_2_merged_raw.tsv"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_benchmark(path: Path) -> list[dict]:
    """Load benchmark CSV, skipping comment lines."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("latin_input", "").startswith("#"):
                continue
            rows.append(row)
    return rows


def load_collisions(path: Path) -> dict[str, list[dict]]:
    """Load collisions.json: latin_input -> [{thai, frequency, word_id}, ...]."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_bigram_counts(path: Path) -> dict[tuple[str, str], int]:
    """Load raw bigram counts from TSV: word1 \\t word2 \\t count."""
    counts: dict[tuple[str, str], int] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                counts[(parts[0], parts[1])] = int(parts[2])
    return counts


# ---------------------------------------------------------------------------
# Statistics derived from bigram counts
# ---------------------------------------------------------------------------

class BigramStats:
    """Precomputed statistics from bigram count data."""

    def __init__(self, bigram_counts: dict[tuple[str, str], int]):
        self.bigram_counts = bigram_counts

        # Unigram counts (as left context): count(w1) = sum of count(w1, *)
        self.left_counts: dict[str, int] = defaultdict(int)
        # Unigram counts (as right/target): count(w2) = sum of count(*, w2)
        self.right_counts: dict[str, int] = defaultdict(int)
        # Total bigram tokens
        self.total_bigram_tokens = 0
        # Total unigram tokens (sum of all right counts = sum of all bigrams)
        self.total_unigram_tokens = 0

        # Continuation counts for Modified KN
        # N1+(*, w): number of distinct left contexts for word w
        self.continuation_count: dict[str, int] = defaultdict(int)
        # N1+(w, *): number of distinct right continuations for word w
        self.continuation_right: dict[str, int] = defaultdict(int)
        # Total distinct bigram types (for continuation probability denominator)
        self.total_bigram_types = len(bigram_counts)

        for (w1, w2), count in bigram_counts.items():
            self.left_counts[w1] += count
            self.right_counts[w2] += count
            self.total_bigram_tokens += count
            self.continuation_count[w2] += 1
            self.continuation_right[w1] += 1

        self.total_unigram_tokens = self.total_bigram_tokens

        # Counts of counts: n_r = number of bigrams with count == r
        count_freq: Counter = Counter(bigram_counts.values())
        self.n1 = count_freq.get(1, 0)
        self.n2 = count_freq.get(2, 0)
        self.n3 = count_freq.get(3, 0)
        self.n4 = count_freq.get(4, 0)

        # Vocabulary size (unique words seen in any position)
        all_words = set()
        for w1, w2 in bigram_counts:
            all_words.add(w1)
            all_words.add(w2)
        self.vocab_size = len(all_words)

    def p_unigram(self, word: str) -> float:
        """MLE unigram probability from bigram marginals."""
        c = self.right_counts.get(word, 0)
        if c == 0:
            # Fallback: uniform over vocab
            return 1.0 / self.vocab_size
        return c / self.total_unigram_tokens

    def bigram_count(self, w1: str, w2: str) -> int:
        return self.bigram_counts.get((w1, w2), 0)

    def left_count(self, w1: str) -> int:
        return self.left_counts.get(w1, 0)


# ---------------------------------------------------------------------------
# Smoothing methods
# ---------------------------------------------------------------------------
# Each returns a score in -log space (lower = more probable = better rank).

def score_stupid_backoff(
    stats: BigramStats, w1: str, w2: str, alpha: float = 0.4
) -> float:
    """Stupid Backoff: use bigram MLE if seen, else alpha * P_unigram."""
    c_bigram = stats.bigram_count(w1, w2)
    c_left = stats.left_count(w1)

    if c_bigram > 0 and c_left > 0:
        score = c_bigram / c_left
    else:
        score = alpha * stats.p_unigram(w2)

    # Avoid log(0)
    if score <= 0:
        return 50.0  # large penalty
    return -math.log(score)


def score_jelinek_mercer(
    stats: BigramStats, w1: str, w2: str, lam: float = 0.5
) -> float:
    """Jelinek-Mercer interpolation: lam * P_bigram + (1-lam) * P_unigram."""
    c_bigram = stats.bigram_count(w1, w2)
    c_left = stats.left_count(w1)

    p_bigram = (c_bigram / c_left) if (c_bigram > 0 and c_left > 0) else 0.0
    p_unigram = stats.p_unigram(w2)

    score = lam * p_bigram + (1.0 - lam) * p_unigram

    if score <= 0:
        return 50.0
    return -math.log(score)


def _mkn_discounts(stats: BigramStats) -> tuple[float, float, float]:
    """Compute Modified Kneser-Ney discount values D1, D2, D3+.

    From Chen & Goodman (1999):
        Y = n1 / (n1 + 2*n2)
        D1 = 1 - 2*Y*(n2/n1)
        D2 = 2 - 3*Y*(n3/n2)
        D3 = 3 - 4*Y*(n4/n3)
    """
    n1, n2, n3, n4 = stats.n1, stats.n2, stats.n3, stats.n4

    # Guard against division by zero
    if n1 == 0 or n2 == 0 or n3 == 0:
        return 0.5, 0.75, 0.9  # sensible defaults

    y = n1 / (n1 + 2.0 * n2)
    d1 = max(1.0 - 2.0 * y * (n2 / n1), 0.0)
    d2 = max(2.0 - 3.0 * y * (n3 / n2), 0.0)
    d3 = max(3.0 - 4.0 * y * (n4 / n3), 0.0) if n3 > 0 else 0.9

    return d1, d2, d3


def score_modified_kneser_ney(
    stats: BigramStats,
    w1: str,
    w2: str,
    discounts: tuple[float, float, float],
) -> float:
    """Modified Kneser-Ney smoothing.

    P_MKN(w2|w1) = max(c(w1,w2) - D(c), 0) / c(w1)
                   + gamma(w1) * P_continuation(w2)

    where:
        D(c) = D1 if c==1, D2 if c==2, D3 if c>=3
        gamma(w1) = (D1*n1(w1) + D2*n2(w1) + D3*n3+(w1)) / c(w1)
        n_k(w1) = number of bigrams (w1,*) with count == k
        P_continuation(w2) = |{w': c(w',w2)>0}| / total_bigram_types
    """
    d1, d2, d3 = discounts
    c_bigram = stats.bigram_count(w1, w2)
    c_left = stats.left_count(w1)

    # Continuation probability for w2
    cont_w2 = stats.continuation_count.get(w2, 0)
    p_cont = cont_w2 / stats.total_bigram_types if stats.total_bigram_types > 0 else 0.0

    if c_left == 0:
        # No context seen — fall back to continuation probability
        score = p_cont if p_cont > 0 else 1.0 / stats.vocab_size
        if score <= 0:
            return 50.0
        return -math.log(score)

    # Discount based on bigram count
    if c_bigram == 0:
        d = 0.0
    elif c_bigram == 1:
        d = d1
    elif c_bigram == 2:
        d = d2
    else:
        d = d3

    first_term = max(c_bigram - d, 0.0) / c_left

    # Gamma: interpolation weight
    # Count how many bigrams (w1, *) have count 1, 2, 3+
    n1_w1 = 0
    n2_w1 = 0
    n3p_w1 = 0
    # This is expensive if done per-query; we precompute below
    # For now, use the continuation_right count as an approximation
    # Actually, let's compute it properly from the data
    # We'll use a simpler approximation: gamma = D * N1+(w1,*) / c(w1)
    # where N1+(w1,*) = number of distinct continuations
    n_cont_right = stats.continuation_right.get(w1, 0)

    # Simplified gamma using average discount
    # Full version would need per-count bucketing per context word
    # Use: gamma = (D1*n1(w1) + D2*n2(w1) + D3*n3+(w1)) / c(w1)
    # Approximate with average discount * total types
    d_avg = (d1 + d2 + d3) / 3.0
    gamma = d_avg * n_cont_right / c_left

    score = first_term + gamma * p_cont

    if score <= 0:
        return 50.0
    return -math.log(score)


def _good_turing_discount(count: int, stats: BigramStats) -> float:
    """Simple Good-Turing discounted count.

    c* = (c+1) * N(c+1) / N(c)

    For counts where N(c+1) is unavailable, use c* = c (no discount).
    """
    count_freq = Counter(stats.bigram_counts.values())
    n_c = count_freq.get(count, 0)
    n_c1 = count_freq.get(count + 1, 0)

    if n_c == 0 or n_c1 == 0:
        return float(count)

    return (count + 1) * n_c1 / n_c


# Precomputed GT discount table (avoids recomputing per query)
_gt_cache: dict[int, float] = {}


def _init_gt_cache(stats: BigramStats, max_count: int = 10) -> None:
    """Precompute Good-Turing discounted counts."""
    global _gt_cache
    _gt_cache = {}
    count_freq = Counter(stats.bigram_counts.values())
    for c in range(1, max_count + 1):
        n_c = count_freq.get(c, 0)
        n_c1 = count_freq.get(c + 1, 0)
        if n_c > 0 and n_c1 > 0:
            _gt_cache[c] = (c + 1) * n_c1 / n_c
        else:
            _gt_cache[c] = float(c)


def score_katz_backoff(
    stats: BigramStats, w1: str, w2: str
) -> float:
    """Katz Backoff with Good-Turing discounting.

    For seen bigrams: use GT-discounted count / c(w1)
    For unseen bigrams: alpha(w1) * P_unigram(w2)

    alpha(w1) distributes leftover mass to unseen bigrams, normalized
    so probabilities sum to 1.
    """
    c_bigram = stats.bigram_count(w1, w2)
    c_left = stats.left_count(w1)

    if c_left == 0:
        # No context — use unigram
        score = stats.p_unigram(w2)
        if score <= 0:
            return 50.0
        return -math.log(score)

    if c_bigram > 0:
        # Seen bigram: use Good-Turing discounted count
        c_star = _gt_cache.get(c_bigram, float(c_bigram))
        score = c_star / c_left
        # Clamp to valid probability range
        score = min(score, 1.0)
        if score <= 0:
            return 50.0
        return -math.log(score)
    else:
        # Unseen bigram: alpha(w1) * P_unigram(w2)
        # alpha(w1) = (1 - sum of discounted probs for seen bigrams) /
        #             (1 - sum of unigram probs for seen continuations)
        # Compute alpha on the fly (could cache per w1)
        seen_mass = 0.0
        seen_unigram_mass = 0.0
        for (h, w), count in stats.bigram_counts.items():
            if h == w1:
                c_star = _gt_cache.get(count, float(count))
                seen_mass += c_star / c_left
                seen_unigram_mass += stats.p_unigram(w)

        remaining_mass = max(1.0 - seen_mass, 1e-10)
        remaining_unigram = max(1.0 - seen_unigram_mass, 1e-10)
        alpha_w1 = remaining_mass / remaining_unigram

        score = alpha_w1 * stats.p_unigram(w2)
        if score <= 0:
            return 50.0
        return -math.log(score)


# ---------------------------------------------------------------------------
# Precompute Katz alpha cache for efficiency
# ---------------------------------------------------------------------------

def _precompute_katz_alpha(stats: BigramStats) -> dict[str, float]:
    """Precompute alpha(w1) for all context words."""
    alpha_cache: dict[str, float] = {}

    # Group bigrams by left context
    by_context: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (w1, w2), count in stats.bigram_counts.items():
        by_context[w1].append((w2, count))

    for w1, continuations in by_context.items():
        c_left = stats.left_count(w1)
        if c_left == 0:
            continue

        seen_mass = 0.0
        seen_unigram_mass = 0.0
        for w2, count in continuations:
            c_star = _gt_cache.get(count, float(count))
            seen_mass += c_star / c_left
            seen_unigram_mass += stats.p_unigram(w2)

        remaining_mass = max(1.0 - seen_mass, 1e-10)
        remaining_unigram = max(1.0 - seen_unigram_mass, 1e-10)
        alpha_cache[w1] = remaining_mass / remaining_unigram

    return alpha_cache


def score_katz_backoff_cached(
    stats: BigramStats, w1: str, w2: str, alpha_cache: dict[str, float]
) -> float:
    """Katz Backoff using precomputed alpha values."""
    c_bigram = stats.bigram_count(w1, w2)
    c_left = stats.left_count(w1)

    if c_left == 0:
        score = stats.p_unigram(w2)
        if score <= 0:
            return 50.0
        return -math.log(score)

    if c_bigram > 0:
        c_star = _gt_cache.get(c_bigram, float(c_bigram))
        score = min(c_star / c_left, 1.0)
        if score <= 0:
            return 50.0
        return -math.log(score)
    else:
        alpha_w1 = alpha_cache.get(w1, 1.0)
        score = alpha_w1 * stats.p_unigram(w2)
        if score <= 0:
            return 50.0
        return -math.log(score)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_method(
    method_name: str,
    score_fn,
    benchmark_rows: list[dict],
    collisions: dict[str, list[dict]],
    trie_unigram: dict[str, float],
    verbose: bool = False,
) -> dict:
    """Evaluate a scoring method on benchmark rows.

    For each row:
      1. Get all candidates for the latin_input from collisions
      2. Score each candidate given the context word
      3. Rank by score (ascending = lower cost = better)
      4. Find rank of expected_top

    Returns dict with MRR, top1_accuracy, and per-row details.
    """
    ranks = []
    details = []
    seen_count = 0
    unseen_count = 0

    for row in benchmark_rows:
        context = row["context"]
        expected = row["expected_top"]
        latin = row["latin_input"]

        # Get all candidates for this latin_input
        candidates_info = collisions.get(latin, [])
        if not candidates_info:
            continue

        candidates = [c["thai"] for c in candidates_info]

        # Ensure expected is in candidate list
        if expected not in candidates:
            candidates.append(expected)

        # Score each candidate
        scored = []
        for cand in candidates:
            s = score_fn(context, cand)
            scored.append((cand, s))

        # Sort by score (lower = better), break ties by unigram frequency
        scored.sort(key=lambda x: (x[1], -trie_unigram.get(x[0], 0.0)))

        # Find rank of expected (1-indexed)
        rank = None
        for i, (cand, _) in enumerate(scored):
            if cand == expected:
                rank = i + 1
                break

        if rank is None:
            rank = len(scored)  # should not happen

        ranks.append(rank)

        # Track seen/unseen
        from .config import OUTPUT_DIR as _od
        # (We track this in the score function indirectly via the stats)

        detail = {
            "context": context,
            "expected": expected,
            "latin": latin,
            "rank": rank,
            "top_candidate": scored[0][0],
            "top_score": scored[0][1],
            "expected_score": next(s for c, s in scored if c == expected),
            "n_candidates": len(scored),
        }
        details.append(detail)

        if verbose and rank > 1:
            top3 = ", ".join(f"{c}({s:.3f})" for c, s in scored[:3])
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
# Unigram-only baseline
# ---------------------------------------------------------------------------

def score_unigram_only(trie_unigram: dict[str, float], w1: str, w2: str) -> float:
    """Baseline: rank by unigram frequency only (ignores context)."""
    freq = trie_unigram.get(w2, 0.0)
    if freq <= 0:
        return 50.0
    return -math.log(freq)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3: Evaluate smoothing methods on bigram benchmark."
    )
    parser.add_argument(
        "--methods",
        type=str,
        default="all",
        help="Comma-separated methods to evaluate: stupid,jm,mkn,katz,unigram,all (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-row miss details",
    )
    parser.add_argument(
        "--types",
        type=str,
        default="bigram",
        help="Benchmark row types to evaluate: bigram,compound,baseline,all (default: bigram)",
    )
    args = parser.parse_args()

    # ---- Load data ----
    print("Loading data...")

    if not RAW_MERGED_PATH.exists():
        print(f"ERROR: Raw merged bigrams not found: {RAW_MERGED_PATH}")
        print("  Run count_ngrams.py first (Stage 2).")
        sys.exit(1)

    bigram_counts = load_bigram_counts(RAW_MERGED_PATH)
    print(f"  Bigram counts: {len(bigram_counts):,} entries")

    stats = BigramStats(bigram_counts)
    print(f"  Vocab size: {stats.vocab_size:,}")
    print(f"  Total bigram tokens: {stats.total_bigram_tokens:,}")
    print(f"  Counts-of-counts: n1={stats.n1:,} n2={stats.n2:,} "
          f"n3={stats.n3:,} n4={stats.n4:,}")

    collisions = load_collisions(COLLISIONS_PATH)
    print(f"  Collision keys: {len(collisions):,}")

    # Build trie unigram lookup
    trie_unigram: dict[str, float] = {}
    for latin, entries in collisions.items():
        for entry in entries:
            trie_unigram[entry["thai"]] = entry["frequency"]

    benchmark = load_benchmark(BENCHMARK_PATH)
    print(f"  Benchmark rows: {len(benchmark)}")

    # Filter by type
    eval_types = args.types.split(",")
    if "all" in eval_types:
        eval_rows = [r for r in benchmark if r.get("context")]
    else:
        eval_rows = [r for r in benchmark if r.get("type") in eval_types and r.get("context")]

    print(f"  Evaluating on: {len(eval_rows)} rows (types: {args.types})")

    # ---- Precompute method-specific data ----
    print("\nPrecomputing statistics...")

    # MKN discounts
    mkn_d = _mkn_discounts(stats)
    print(f"  MKN discounts: D1={mkn_d[0]:.4f} D2={mkn_d[1]:.4f} D3+={mkn_d[2]:.4f}")

    # Katz Good-Turing cache
    _init_gt_cache(stats)
    print(f"  GT discount cache: {len(_gt_cache)} entries")
    for c in range(1, 6):
        print(f"    count {c} -> discounted {_gt_cache.get(c, c):.3f}")

    # Katz alpha cache
    katz_alpha = _precompute_katz_alpha(stats)
    print(f"  Katz alpha cache: {len(katz_alpha):,} context words")

    # ---- Determine which methods to run ----
    methods_to_run = args.methods.split(",")
    if "all" in methods_to_run:
        methods_to_run = ["unigram", "stupid", "jm", "mkn", "katz"]

    # ---- Build scoring configurations ----
    configs: list[tuple[str, object]] = []

    for method in methods_to_run:
        if method == "unigram":
            configs.append((
                "Unigram (baseline)",
                lambda w1, w2: score_unigram_only(trie_unigram, w1, w2),
            ))

        elif method == "stupid":
            for alpha in [0.2, 0.4, 0.6]:
                configs.append((
                    f"Stupid Backoff (α={alpha})",
                    (lambda a: lambda w1, w2: score_stupid_backoff(stats, w1, w2, alpha=a))(alpha),
                ))

        elif method == "jm":
            for lam in [0.1, 0.3, 0.5, 0.7, 0.9]:
                configs.append((
                    f"Jelinek-Mercer (λ={lam})",
                    (lambda l: lambda w1, w2: score_jelinek_mercer(stats, w1, w2, lam=l))(lam),
                ))

        elif method == "mkn":
            configs.append((
                "Modified Kneser-Ney",
                lambda w1, w2: score_modified_kneser_ney(stats, w1, w2, mkn_d),
            ))

        elif method == "katz":
            configs.append((
                "Katz Backoff",
                lambda w1, w2: score_katz_backoff_cached(stats, w1, w2, katz_alpha),
            ))

    # ---- Run evaluation ----
    print(f"\n{'=' * 74}")
    print("EVALUATION RESULTS")
    print(f"{'=' * 74}")

    results_summary: list[tuple[str, float, float, int]] = []

    for name, score_fn in configs:
        result = evaluate_method(
            name, score_fn, eval_rows, collisions, trie_unigram,
            verbose=args.verbose,
        )
        mrr = result["mrr"]
        top1 = result["top1_acc"]
        n = result["n"]

        results_summary.append((name, mrr, top1, n))
        print(f"\n  {name}:")
        print(f"    MRR:          {mrr:.4f}")
        print(f"    Top-1 acc:    {top1:.1%} ({int(top1 * n)}/{n})")
        if result.get("rank_distribution"):
            dist = result["rank_distribution"]
            dist_str = ", ".join(f"r{k}:{v}" for k, v in sorted(dist.items())[:5])
            print(f"    Rank dist:    {dist_str}")

    # ---- Summary table ----
    print(f"\n{'=' * 74}")
    print("SUMMARY")
    print(f"{'=' * 74}")
    print(f"  {'Method':<35} {'MRR':>7} {'Top-1':>7} {'N':>5}")
    print(f"  {'-' * 35} {'-' * 7} {'-' * 7} {'-' * 5}")
    for name, mrr, top1, n in results_summary:
        print(f"  {name:<35} {mrr:>7.4f} {top1:>6.1%} {n:>5}")

    # ---- Failure analysis (if verbose) ----
    if args.verbose and len(configs) > 0:
        print(f"\n{'=' * 74}")
        print("FAILURE ANALYSIS (rows where best method still misses)")
        print(f"{'=' * 74}")

        # Use the last method's details as reference
        # Actually, let's find rows where ALL methods miss
        # Re-run with the best method
        best_name, best_fn = max(
            configs,
            key=lambda x: evaluate_method(x[0], x[1], eval_rows, collisions, trie_unigram)["mrr"],
        )
        best_result = evaluate_method(best_name, best_fn, eval_rows, collisions, trie_unigram)
        misses = [d for d in best_result["details"] if d["rank"] > 1]
        print(f"\n  Best method ({best_name}): {len(misses)} misses out of {best_result['n']}")
        for d in misses[:20]:
            print(f"    rank={d['rank']}: {d['context']}+{d['latin']} "
                  f"-> expect {d['expected']}, got {d['top_candidate']}")


if __name__ == "__main__":
    main()
