"""Position-based Viterbi beam search for smoke testing.

Given a Latin input string, builds a word lattice from trie prefix matches
and finds the lowest-cost segmentation path using the same scoring formula
as the thaime engine: cost-based (lower = better), natural log, segmentation
penalty (LAMBDA), and weighted n-gram bonus.

Reference: docs/.plans/thaime-engine-candidate-selection-handover.md
"""

from __future__ import annotations

import math
from collections import defaultdict

from src.utils.smoke_test.ngram_score import NgramModel
from src.utils.smoke_test.trie_lookup import TrieData

# Engine parameters (from config.rs defaults)
LAMBDA = 1.0
MIN_FREQ = 5e-6
NGRAM_WEIGHT = 2.0
BEAM_MULTIPLIER = 4


def beam_search(
    input_text: str,
    trie: TrieData,
    model: NgramModel,
    beam_width: int = 10,
) -> list[tuple[str, float]]:
    """Run position-based Viterbi beam search over a Latin input string.

    Matches the thaime engine's candidate selection logic:
    - Builds a word lattice from trie prefix matches
    - Forward pass with cost-based scoring (lower = better)
    - Per-state and global beam pruning
    - Deduplication by Thai output

    Args:
        input_text: Latin romanization string (no spaces).
        trie: Loaded trie dataset with prefix index.
        model: Loaded n-gram model for scoring.
        beam_width: K parameter — candidates per state and final output count.

    Returns:
        List of (thai_output, cost) pairs, sorted by cost ascending (lower = better).
    """
    input_lower = input_text.lower()
    n = len(input_lower)

    if n == 0:
        return []

    # Stage 1: Build lattice — edges grouped by end position
    # Each edge: (start, entry, rom_len)
    edges_by_end: dict[int, list[tuple[int, object, int]]] = defaultdict(list)
    for start in range(n):
        matches = trie.prefix_match(input_lower, start)
        for entry, rom in matches:
            end = start + len(rom)
            edges_by_end[end].append((start, entry, len(rom)))

    # Stage 2: Viterbi forward pass
    # State at each position: (prev_word_2, prev_word_1) -> list of (cost, words)
    # prev_word_2 and prev_word_1 are Thai strings (or None at BOS)
    best: list[dict[tuple[str | None, str | None], list[tuple[float, list[str]]]]] = [
        defaultdict(list) for _ in range(n + 1)
    ]
    best[0][(None, None)].append((0.0, []))

    global_beam = beam_width * BEAM_MULTIPLIER

    for end in range(1, n + 1):
        new_states: dict[tuple[str | None, str | None], list[tuple[float, list[str]]]] = (
            defaultdict(list)
        )

        for start, entry, rom_len in edges_by_end[end]:
            if not best[start]:
                continue

            # Precompute unigram cost for this edge
            freq = entry.frequency
            unigram_cost = -math.log(max(freq, MIN_FREQ)) + LAMBDA

            for state, paths in best[start].items():
                prev2, prev1 = state

                # Compute n-gram bonus once per (state, word) pair
                sbo_score = model.trigram_score(prev2, prev1, entry.thai)
                ngram_bonus = NGRAM_WEIGHT * -math.log(max(sbo_score, 1e-20))
                edge_cost = unigram_cost + ngram_bonus

                for path_cost, path_words in paths:
                    new_cost = path_cost + edge_cost
                    new_words = path_words + [entry.thai]
                    new_state = (prev1, entry.thai)
                    new_states[new_state].append((new_cost, new_words))

        # Per-state pruning: keep top K per state (lowest cost)
        for state in new_states:
            new_states[state].sort(key=lambda x: x[0])
            new_states[state] = new_states[state][:beam_width]

        # Global beam pruning
        total = sum(len(paths) for paths in new_states.values())
        if total > global_beam:
            all_entries = []
            for state, paths in new_states.items():
                for cost, words in paths:
                    all_entries.append((cost, state, words))
            all_entries.sort(key=lambda x: x[0])
            all_entries = all_entries[:global_beam]

            # Redistribute into state buckets
            pruned: dict[tuple[str | None, str | None], list[tuple[float, list[str]]]] = (
                defaultdict(list)
            )
            for cost, state, words in all_entries:
                pruned[state].append((cost, words))
            new_states = pruned

        best[end] = new_states

    # Stage 3: Collect complete paths at position n
    all_paths: list[tuple[float, list[str]]] = []
    for paths in best[n].values():
        all_paths.extend(paths)
    all_paths.sort(key=lambda x: x[0])

    # Deduplicate by Thai output, keeping lowest cost
    seen: set[str] = set()
    results: list[tuple[str, float]] = []
    for cost, words in all_paths:
        thai = "".join(words)
        if thai not in seen:
            seen.add(thai)
            results.append((thai, cost))
        if len(results) >= beam_width:
            break

    return results
