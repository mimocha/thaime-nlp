"""Diagnostic analysis of benchmark bias and method behavior.

Breaks down evaluation results by:
  1. Per latin_input group MRR
  2. Seen vs unseen bigram split
  3. Dominant-word frequency analysis
  4. Score differentiation (does context actually change rankings vs unigram?)

Usage:
    python -m experiments.007-bigram-scoring.scripts.diagnose_benchmark
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .config import OUTPUT_DIR, TRIE_DATASET_PATH
from .evaluate_smoothing import (
    BigramStats,
    load_benchmark,
    load_bigram_counts,
    load_collisions,
    score_stupid_backoff,
    score_jelinek_mercer,
    score_modified_kneser_ney,
    score_katz_backoff_cached,
    score_unigram_only,
    _mkn_discounts,
    _init_gt_cache,
    _precompute_katz_alpha,
    BENCHMARK_PATH,
    RAW_MERGED_PATH,
    COLLISIONS_PATH,
)


def main() -> None:
    # ---- Load data ----
    print("Loading data...")
    bigram_counts = load_bigram_counts(RAW_MERGED_PATH)
    stats = BigramStats(bigram_counts)
    collisions = load_collisions(COLLISIONS_PATH)

    trie_unigram: dict[str, float] = {}
    for latin, entries in collisions.items():
        for entry in entries:
            trie_unigram[entry["thai"]] = entry["frequency"]

    benchmark = load_benchmark(BENCHMARK_PATH)
    bigram_rows = [r for r in benchmark if r.get("type") == "bigram" and r.get("context")]

    print(f"  {len(bigram_rows)} bigram-type rows")
    print(f"  {len(bigram_counts):,} bigram entries")
    print(f"  Vocab: {stats.vocab_size:,}")

    # Precompute
    mkn_d = _mkn_discounts(stats)
    _init_gt_cache(stats)
    katz_alpha = _precompute_katz_alpha(stats)

    # ---- 1. Per-group analysis ----
    print(f"\n{'=' * 74}")
    print("1. PER-GROUP BREAKDOWN (Stupid Backoff α=0.4)")
    print(f"{'=' * 74}")

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in bigram_rows:
        groups[row["latin_input"]].append(row)

    group_stats = []
    for latin, rows in sorted(groups.items()):
        ranks = []
        seen_count = 0
        unseen_count = 0
        for row in rows:
            ctx = row["context"]
            exp = row["expected_top"]
            candidates_info = collisions.get(latin, [])
            candidates = [c["thai"] for c in candidates_info]
            if exp not in candidates:
                candidates.append(exp)

            # Check if expected bigram is seen
            is_seen = stats.bigram_count(ctx, exp) > 0

            if is_seen:
                seen_count += 1
            else:
                unseen_count += 1

            scored = [(c, score_stupid_backoff(stats, ctx, c, alpha=0.4)) for c in candidates]
            scored.sort(key=lambda x: (x[1], -trie_unigram.get(x[0], 0.0)))
            rank = next(i + 1 for i, (c, _) in enumerate(scored) if c == exp)
            ranks.append(rank)

        n = len(ranks)
        mrr = sum(1.0 / r for r in ranks) / n
        top1 = sum(1 for r in ranks if r == 1) / n
        n_candidates = len(collisions.get(latin, []))

        group_stats.append((latin, n, mrr, top1, seen_count, unseen_count, n_candidates))

    print(f"\n  {'Group':<8} {'N':>3} {'MRR':>6} {'Top1':>6} {'Seen':>5} {'Unseen':>6} {'Cands':>5}")
    print(f"  {'-'*8} {'-'*3} {'-'*6} {'-'*6} {'-'*5} {'-'*6} {'-'*5}")
    for latin, n, mrr, top1, seen, unseen, cands in group_stats:
        print(f"  {latin:<8} {n:>3} {mrr:>6.3f} {top1:>5.0%} {seen:>5} {unseen:>6} {cands:>5}")

    total_seen = sum(s[4] for s in group_stats)
    total_unseen = sum(s[5] for s in group_stats)
    print(f"\n  Total seen: {total_seen}, unseen: {total_unseen} "
          f"({total_seen/(total_seen+total_unseen):.1%} seen)")

    # ---- 2. Seen vs Unseen split ----
    print(f"\n{'=' * 74}")
    print("2. SEEN vs UNSEEN BIGRAM SPLIT (all methods)")
    print(f"{'=' * 74}")

    methods = [
        ("Unigram",       lambda w1, w2: score_unigram_only(trie_unigram, w1, w2)),
        ("Stupid α=0.4",  lambda w1, w2: score_stupid_backoff(stats, w1, w2, 0.4)),
        ("JM λ=0.7",      lambda w1, w2: score_jelinek_mercer(stats, w1, w2, 0.7)),
        ("JM λ=0.9",      lambda w1, w2: score_jelinek_mercer(stats, w1, w2, 0.9)),
        ("MKN",           lambda w1, w2: score_modified_kneser_ney(stats, w1, w2, mkn_d)),
        ("Katz",          lambda w1, w2: score_katz_backoff_cached(stats, w1, w2, katz_alpha)),
    ]

    for name, score_fn in methods:
        seen_ranks = []
        unseen_ranks = []
        for row in bigram_rows:
            ctx = row["context"]
            exp = row["expected_top"]
            latin = row["latin_input"]
            candidates_info = collisions.get(latin, [])
            candidates = [c["thai"] for c in candidates_info]
            if exp not in candidates:
                candidates.append(exp)

            scored = [(c, score_fn(ctx, c)) for c in candidates]
            scored.sort(key=lambda x: (x[1], -trie_unigram.get(x[0], 0.0)))
            rank = next(i + 1 for i, (c, _) in enumerate(scored) if c == exp)

            if stats.bigram_count(ctx, exp) > 0:
                seen_ranks.append(rank)
            else:
                unseen_ranks.append(rank)

        def _mrr(ranks):
            return sum(1.0/r for r in ranks) / len(ranks) if ranks else 0.0
        def _top1(ranks):
            return sum(1 for r in ranks if r == 1) / len(ranks) if ranks else 0.0

        print(f"\n  {name}:")
        print(f"    Seen ({len(seen_ranks):>3}):   MRR={_mrr(seen_ranks):.4f}  "
              f"Top-1={_top1(seen_ranks):.1%} ({sum(1 for r in seen_ranks if r==1)}/{len(seen_ranks)})")
        print(f"    Unseen ({len(unseen_ranks):>3}): MRR={_mrr(unseen_ranks):.4f}  "
              f"Top-1={_top1(unseen_ranks):.1%} ({sum(1 for r in unseen_ranks if r==1)}/{len(unseen_ranks)})")

    # ---- 3. Dominant word analysis ----
    print(f"\n{'=' * 74}")
    print("3. DOMINANT WORD ANALYSIS")
    print(f"{'=' * 74}")
    print("  For each latin_input, the unigram-dominant word and how often it")
    print("  blocks the correct answer:")

    for latin, rows in sorted(groups.items()):
        candidates_info = collisions.get(latin, [])
        if not candidates_info:
            continue

        # Find the dominant candidate (highest unigram freq)
        dominant = max(candidates_info, key=lambda c: c["frequency"])
        dom_word = dominant["thai"]
        dom_freq = dominant["frequency"]

        # How many rows have a different expected_top?
        n_not_dominant = sum(1 for r in rows if r["expected_top"] != dom_word)
        n_total = len(rows)

        # For rows where expected != dominant, how many does Stupid Backoff get right?
        non_dom_correct = 0
        for row in rows:
            if row["expected_top"] == dom_word:
                continue
            ctx = row["context"]
            exp = row["expected_top"]
            candidates = [c["thai"] for c in candidates_info]
            if exp not in candidates:
                candidates.append(exp)
            scored = [(c, score_stupid_backoff(stats, ctx, c, 0.4)) for c in candidates]
            scored.sort(key=lambda x: (x[1], -trie_unigram.get(x[0], 0.0)))
            if scored[0][0] == exp:
                non_dom_correct += 1

        print(f"  {latin:<8} dominant={dom_word} (freq={dom_freq:.4e}), "
              f"{n_not_dominant}/{n_total} rows need to beat it, "
              f"{non_dom_correct}/{n_not_dominant} succeed")

    # ---- 4. Context differentiation check ----
    print(f"\n{'=' * 74}")
    print("4. CONTEXT DIFFERENTIATION (does context change the ranking?)")
    print(f"{'=' * 74}")
    print("  Rows where Stupid Backoff produces the SAME top-1 as Unigram")
    print("  (i.e., context had no effect on the winner):")

    same_as_unigram = 0
    diff_from_unigram = 0
    diff_and_correct = 0
    diff_and_wrong = 0

    for row in bigram_rows:
        ctx = row["context"]
        exp = row["expected_top"]
        latin = row["latin_input"]
        candidates_info = collisions.get(latin, [])
        candidates = [c["thai"] for c in candidates_info]
        if exp not in candidates:
            candidates.append(exp)

        # Unigram ranking
        uni_scored = [(c, score_unigram_only(trie_unigram, ctx, c)) for c in candidates]
        uni_scored.sort(key=lambda x: (x[1], -trie_unigram.get(x[0], 0.0)))
        uni_top = uni_scored[0][0]

        # Stupid Backoff ranking
        sb_scored = [(c, score_stupid_backoff(stats, ctx, c, 0.4)) for c in candidates]
        sb_scored.sort(key=lambda x: (x[1], -trie_unigram.get(x[0], 0.0)))
        sb_top = sb_scored[0][0]

        if sb_top == uni_top:
            same_as_unigram += 1
        else:
            diff_from_unigram += 1
            if sb_top == exp:
                diff_and_correct += 1
            else:
                diff_and_wrong += 1

    total = same_as_unigram + diff_from_unigram
    print(f"\n  Same top-1 as unigram:      {same_as_unigram}/{total} "
          f"({same_as_unigram/total:.1%}) — context had no effect")
    print(f"  Different top-1 from unigram: {diff_from_unigram}/{total} "
          f"({diff_from_unigram/total:.1%}) — context changed the winner")
    print(f"    Of those, correct:  {diff_and_correct} "
          f"({diff_and_correct/diff_from_unigram:.1%} of changed)" if diff_from_unigram > 0 else "")
    print(f"    Of those, wrong:    {diff_and_wrong} "
          f"({diff_and_wrong/diff_from_unigram:.1%} of changed)" if diff_from_unigram > 0 else "")

    # ---- 5. Score distribution for seen bigrams ----
    print(f"\n{'=' * 74}")
    print("5. SEEN BIGRAM COUNT DISTRIBUTION")
    print(f"{'=' * 74}")
    print("  For rows where the expected bigram IS seen, what are the counts?")

    seen_counts = []
    for row in bigram_rows:
        ctx = row["context"]
        exp = row["expected_top"]
        c = stats.bigram_count(ctx, exp)
        if c > 0:
            seen_counts.append((ctx, exp, c, row["latin_input"]))

    seen_counts.sort(key=lambda x: x[2])
    print(f"\n  {'Context':<12} {'Expected':<12} {'Count':>8} {'Group':<8}")
    print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*8}")
    for ctx, exp, c, latin in seen_counts[:20]:
        print(f"  {ctx:<12} {exp:<12} {c:>8,} {latin:<8}")
    if len(seen_counts) > 20:
        print(f"  ... ({len(seen_counts)} total seen bigrams)")
    print(f"\n  Count percentiles:")
    counts_only = [c for _, _, c, _ in seen_counts]
    if counts_only:
        counts_only.sort()
        n = len(counts_only)
        for p in [0, 25, 50, 75, 100]:
            idx = min(int(n * p / 100), n - 1)
            print(f"    p{p:>3}: {counts_only[idx]:>8,}")


if __name__ == "__main__":
    main()
