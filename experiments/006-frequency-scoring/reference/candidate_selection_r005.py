"""
Candidate Selection Algorithm Prototype for THAIME

Demonstrates the recommended Viterbi-based candidate selection algorithm
for finding and ranking Thai word/phrase candidates from a Latin input string.

This prototype works with a synthetic/mock dictionary and manually constructed
lattices. It validates the algorithm design before Rust implementation.

Usage:
    python candidate_selection.py

Algorithm:
    1. Build a word lattice from common prefix search results
    2. Use modified Viterbi (dynamic programming) to find top-k paths
    3. Score paths using: -sum(log(freq)) + num_words * segmentation_penalty
    4. Return ranked candidates

Author: THAIME Research
Date: 2026-03-09
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LatticeEdge:
    """A single edge in the word lattice.

    Represents a Thai word that matches a substring of the Latin input.
    """
    start: int          # Start position in the Latin input string
    end: int            # End position (exclusive) in the Latin input string
    word_id: int        # Unique word identifier
    thai_text: str      # Thai text for this word
    frequency: float    # Corpus frequency (0.0 to 1.0, normalized)
    romanization: str   # The Latin substring that matched


@dataclass
class ScoredPath:
    """A complete path through the lattice with its score."""
    edges: list[LatticeEdge]
    score: float        # Lower is better (negative log-likelihood + penalty)
    thai_text: str = ""

    def __post_init__(self):
        if not self.thai_text and self.edges:
            self.thai_text = "".join(e.thai_text for e in self.edges)


# ---------------------------------------------------------------------------
# Mock dictionary
# ---------------------------------------------------------------------------

# Mock dictionary entries: (thai_text, romanization_key, frequency, word_id)
# Frequencies are synthetic but reflect realistic relative ordering.
MOCK_DICTIONARY: list[tuple[str, str, float, int]] = [
    # Common words
    ("คน", "khon", 0.0085, 1),
    ("ของ", "khong", 0.0120, 2),
    ("ดี", "dee", 0.0070, 3),
    ("ดี", "dii", 0.0070, 3),
    ("ไป", "pai", 0.0065, 4),
    ("มา", "maa", 0.0072, 5),
    ("มา", "ma", 0.0072, 5),
    ("ไม่", "mai", 0.0090, 6),
    ("น้ำ", "nam", 0.0040, 7),
    ("น้ำ", "naam", 0.0040, 7),

    # rongrean test case
    ("โรงเรียน", "rongrean", 0.0025, 10),
    ("โรงเรียน", "rongrian", 0.0025, 10),
    ("โรง", "rong", 0.0018, 11),
    ("เรียน", "rean", 0.0015, 12),
    ("เรียน", "rian", 0.0015, 12),

    # sawatdee test case
    ("สวัสดี", "sawatdee", 0.0030, 20),
    ("สวัสดี", "sawatdi", 0.0030, 20),
    ("สวัส", "sawat", 0.0002, 21),

    # prathet test case
    ("ประเทศ", "prathet", 0.0035, 30),
    ("ประ", "pra", 0.0008, 31),
    ("เทศ", "thet", 0.0006, 32),

    # Ambiguous test case: maikan
    # Note: ไม่ "mai" (word_id 6) already defined above in common words
    ("ไม้กั้น", "maikan", 0.0003, 40),
    ("กัน", "kan", 0.0045, 41),
    ("ไม", "mai", 0.0005, 42),
    ("กั้น", "kan", 0.0004, 43),

    # Context: common short words that may appear in lattices
    ("ที่", "thi", 0.0095, 50),
    ("ที่", "thee", 0.0095, 50),
    ("ใน", "nai", 0.0080, 51),
    ("จะ", "ja", 0.0060, 52),
    ("จะ", "cha", 0.0060, 52),
    ("เป็น", "pen", 0.0075, 53),
    ("เป็น", "ben", 0.0075, 53),
    ("ได้", "dai", 0.0068, 54),
    ("ได้", "daai", 0.0068, 54),
    ("แล้ว", "laew", 0.0042, 55),
    ("แล้ว", "laeo", 0.0042, 55),
    ("กิน", "kin", 0.0032, 56),
    ("กิน", "gin", 0.0032, 56),
    ("อยู่", "yuu", 0.0038, 57),
    ("อยู่", "yu", 0.0038, 57),
    ("หมู", "muu", 0.0012, 58),
    ("หมู", "moo", 0.0012, 58),
    ("ข้าว", "khaaw", 0.0028, 59),
    ("ข้าว", "khao", 0.0028, 59),
    ("ข้าว", "kao", 0.0028, 59),

    # Additional for longer input test
    ("บ้าน", "baan", 0.0022, 60),
    ("บ้าน", "ban", 0.0022, 60),
    ("หนังสือ", "nangsuue", 0.0010, 61),
    ("หนังสือ", "nangsue", 0.0010, 61),
]


def build_prefix_index(
    dictionary: list[tuple[str, str, float, int]],
) -> dict[str, list[tuple[str, float, int]]]:
    """Build a simple prefix lookup from the mock dictionary.

    Returns a mapping: romanization_key -> [(thai_text, frequency, word_id), ...]
    """
    index: dict[str, list[tuple[str, float, int]]] = {}
    for thai, roman, freq, wid in dictionary:
        if roman not in index:
            index[roman] = []
        index[roman].append((thai, freq, wid))
    return index


# ---------------------------------------------------------------------------
# Lattice construction
# ---------------------------------------------------------------------------

def build_lattice(
    latin_input: str,
    dictionary: list[tuple[str, str, float, int]] | None = None,
) -> list[LatticeEdge]:
    """Build a word lattice via common prefix search on the input string.

    For each starting position in the input, find all dictionary entries
    whose romanization key matches a prefix starting at that position.

    Args:
        latin_input: The Latin input string (e.g., "rongrean")
        dictionary: Optional dictionary entries; defaults to MOCK_DICTIONARY

    Returns:
        List of LatticeEdge objects representing all matching entries.
    """
    if dictionary is None:
        dictionary = MOCK_DICTIONARY

    index = build_prefix_index(dictionary)
    edges: list[LatticeEdge] = []
    input_len = len(latin_input)

    for start in range(input_len):
        # Check all possible substrings from this position
        for end in range(start + 1, input_len + 1):
            substring = latin_input[start:end]
            if substring in index:
                for thai_text, freq, word_id in index[substring]:
                    edges.append(LatticeEdge(
                        start=start,
                        end=end,
                        word_id=word_id,
                        thai_text=thai_text,
                        frequency=freq,
                        romanization=substring,
                    ))

    return edges


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# Minimum frequency floor to prevent -inf for zero-frequency words
MIN_FREQUENCY = 1e-7

# Default segmentation penalty: added per word in the path.
# Positive value penalizes paths with more words (discourages over-segmentation).
# Tuned empirically: 0.5 works well for typical Thai IME inputs.
DEFAULT_SEGMENTATION_PENALTY = 0.5


def edge_cost(edge: LatticeEdge) -> float:
    """Compute the cost of a single lattice edge.

    Cost = -log(frequency)

    Lower frequency → higher cost. This is the unigram negative
    log-likelihood component of the scoring model.
    """
    freq = max(edge.frequency, MIN_FREQUENCY)
    return -math.log(freq)


def path_score(
    edges: list[LatticeEdge],
    segmentation_penalty: float = DEFAULT_SEGMENTATION_PENALTY,
) -> float:
    """Compute the total score for a path through the lattice.

    Score = sum(-log(freq_i)) + num_words * segmentation_penalty

    Lower is better.

    Args:
        edges: List of edges forming a complete path
        segmentation_penalty: Per-word penalty to discourage over-segmentation

    Returns:
        Total path score (lower is better)
    """
    total = sum(edge_cost(e) for e in edges)
    total += len(edges) * segmentation_penalty
    return total


# ---------------------------------------------------------------------------
# Candidate selection algorithms
# ---------------------------------------------------------------------------

def viterbi_top_k(
    latin_input: str,
    lattice: list[LatticeEdge],
    k: int = 10,
    segmentation_penalty: float = DEFAULT_SEGMENTATION_PENALTY,
) -> list[ScoredPath]:
    """Find the top-k best paths through the lattice using modified Viterbi.

    This is the recommended algorithm for THAIME MVP. It uses dynamic
    programming to find the k-best paths efficiently.

    Algorithm:
        1. Group edges by their end position.
        2. For each position p (left to right), maintain the k-best
           partial paths that end at position p.
        3. At the final position (len(input)), extract and return the
           k-best complete paths.

    Complexity: O(|E| * k) where |E| is the number of lattice edges.

    Args:
        latin_input: The Latin input string
        lattice: List of lattice edges from build_lattice()
        k: Number of top candidates to return
        segmentation_penalty: Per-word penalty

    Returns:
        List of ScoredPath objects, sorted by score (best first).
    """
    input_len = len(latin_input)

    # Group edges by their start position for efficient lookup
    edges_from: dict[int, list[LatticeEdge]] = {}
    for edge in lattice:
        if edge.start not in edges_from:
            edges_from[edge.start] = []
        edges_from[edge.start].append(edge)

    # best_paths_at[pos] = list of (score, edge_list) for the k-best paths
    # that end at position `pos`
    best_paths_at: dict[int, list[tuple[float, list[LatticeEdge]]]] = {
        0: [(0.0, [])],  # Start: zero cost, empty path
    }

    # Process positions left to right
    for pos in range(input_len):
        if pos not in best_paths_at:
            continue

        if pos not in edges_from:
            continue

        for edge in edges_from[pos]:
            cost = edge_cost(edge) + segmentation_penalty

            for prev_score, prev_path in best_paths_at[pos]:
                new_score = prev_score + cost
                new_path = prev_path + [edge]

                end = edge.end
                if end not in best_paths_at:
                    best_paths_at[end] = []

                best_paths_at[end].append((new_score, new_path))

                # Keep only the k-best at each position (pruning)
                if len(best_paths_at[end]) > k:
                    best_paths_at[end].sort(key=lambda x: x[0])
                    best_paths_at[end] = best_paths_at[end][:k]

    # Extract complete paths (those ending at the final position)
    if input_len not in best_paths_at:
        return []

    results = best_paths_at[input_len]
    results.sort(key=lambda x: x[0])

    return [
        ScoredPath(edges=path, score=score)
        for score, path in results[:k]
    ]


def exhaustive_search(
    latin_input: str,
    lattice: list[LatticeEdge],
    k: int = 10,
    segmentation_penalty: float = DEFAULT_SEGMENTATION_PENALTY,
    max_paths: int = 1000,
) -> list[ScoredPath]:
    """Find top-k paths by exhaustive DFS enumeration (reference implementation).

    This is the simplest algorithm — it enumerates all valid paths and
    returns the top-k. Used as a correctness reference for the Viterbi
    implementation.

    Warning: Exponential worst-case. The max_paths parameter provides
    a safety limit.

    Args:
        latin_input: The Latin input string
        lattice: List of lattice edges
        k: Number of top candidates to return
        segmentation_penalty: Per-word penalty
        max_paths: Maximum paths to enumerate before stopping

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

    all_paths: list[tuple[float, list[LatticeEdge]]] = []

    def dfs(pos: int, current_path: list[LatticeEdge], current_score: float):
        if len(all_paths) >= max_paths:
            return

        if pos == input_len:
            all_paths.append((current_score, list(current_path)))
            return

        if pos not in edges_from:
            return

        for edge in edges_from[pos]:
            cost = edge_cost(edge) + segmentation_penalty
            current_path.append(edge)
            dfs(edge.end, current_path, current_score + cost)
            current_path.pop()

    dfs(0, [], 0.0)

    all_paths.sort(key=lambda x: x[0])
    return [
        ScoredPath(edges=path, score=score)
        for score, path in all_paths[:k]
    ]


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------

def convert(
    latin_input: str,
    k: int = 10,
    segmentation_penalty: float = DEFAULT_SEGMENTATION_PENALTY,
    dictionary: list[tuple[str, str, float, int]] | None = None,
) -> list[ScoredPath]:
    """High-level API: convert a Latin input string to ranked Thai candidates.

    Args:
        latin_input: The Latin input string (e.g., "rongrean")
        k: Number of top candidates to return
        segmentation_penalty: Per-word penalty (default 0.5)
        dictionary: Optional custom dictionary; defaults to MOCK_DICTIONARY

    Returns:
        List of ScoredPath objects, sorted by score (best first).
        Empty list if no valid segmentation exists.
    """
    lattice = build_lattice(latin_input, dictionary)
    return viterbi_top_k(latin_input, lattice, k, segmentation_penalty)


# ---------------------------------------------------------------------------
# Performance measurement
# ---------------------------------------------------------------------------

def measure_performance(
    n_edges_list: list[int] | None = None,
    n_runs: int = 100,
) -> dict[int, dict[str, float]]:
    """Measure scoring performance on synthetic lattices of various sizes.

    Generates synthetic lattices with the specified number of edges and
    measures the time for viterbi_top_k to find top-10 paths.

    Args:
        n_edges_list: List of lattice sizes to test
        n_runs: Number of timing runs per size

    Returns:
        Dict mapping edge count to timing stats (mean_us, median_us, p99_us)
    """
    if n_edges_list is None:
        n_edges_list = [10, 25, 50, 100, 200]

    results: dict[int, dict[str, float]] = {}

    for n_edges in n_edges_list:
        # Generate a synthetic lattice with n_edges edges
        # Simulate a 30-character input with overlapping edges
        input_len = max(30, n_edges // 3)
        edges: list[LatticeEdge] = []
        for i in range(n_edges):
            start = i % (input_len - 1)
            length = min(1 + (i % 5), input_len - start)
            end = start + length
            edges.append(LatticeEdge(
                start=start,
                end=end,
                word_id=i,
                thai_text=f"word_{i}",
                frequency=max(0.0001, 0.01 - i * 0.0001),
                romanization=f"r{i}",
            ))

        latin_input = "a" * input_len

        # Warm up
        viterbi_top_k(latin_input, edges, k=10)

        # Timed runs
        times: list[float] = []
        for _ in range(n_runs):
            t0 = time.perf_counter_ns()
            viterbi_top_k(latin_input, edges, k=10)
            t1 = time.perf_counter_ns()
            times.append((t1 - t0) / 1000.0)  # Convert to microseconds

        times.sort()
        mean_us = sum(times) / len(times)
        median_us = times[len(times) // 2]
        p99_us = times[int(len(times) * 0.99)]

        results[n_edges] = {
            "mean_us": round(mean_us, 1),
            "median_us": round(median_us, 1),
            "p99_us": round(p99_us, 1),
            "input_len": input_len,
        }

    return results


# ---------------------------------------------------------------------------
# Main: demo and validation
# ---------------------------------------------------------------------------

def main():
    """Run the prototype demonstration."""
    print("=" * 70)
    print("THAIME Candidate Selection Algorithm Prototype")
    print("=" * 70)

    # --- Demo conversions ---
    test_inputs = [
        ("rongrean", "โรงเรียน"),
        ("sawatdee", "สวัสดี"),
        ("prathet", "ประเทศ"),
        ("khon", "คน"),
        ("maikan", "ไม้กั้น / ไม่+กัน (ambiguous)"),
    ]

    print("\n--- Conversion Results ---\n")

    for latin_input, expected in test_inputs:
        candidates = convert(latin_input, k=5)
        print(f"Input: '{latin_input}'  (expected: {expected})")

        if not candidates:
            print("  No valid candidates found.\n")
            continue

        lattice = build_lattice(latin_input)
        print(f"  Lattice: {len(lattice)} edges")

        for i, cand in enumerate(candidates):
            words = " + ".join(e.thai_text for e in cand.edges)
            n_words = len(cand.edges)
            print(f"  #{i+1}: {cand.thai_text}  "
                  f"(score={cand.score:.3f}, words={n_words}, "
                  f"decomposition={words})")
        print()

    # --- Performance measurement ---
    print("--- Performance Measurement ---\n")
    print("Measuring viterbi_top_k (k=10) on synthetic lattices...\n")

    perf = measure_performance()
    print(f"{'Edges':>8} | {'Input Len':>9} | {'Mean (µs)':>10} | "
          f"{'Median (µs)':>11} | {'P99 (µs)':>9}")
    print("-" * 60)
    for n_edges, stats in sorted(perf.items()):
        print(f"{n_edges:>8} | {stats['input_len']:>9} | "
              f"{stats['mean_us']:>10.1f} | {stats['median_us']:>11.1f} | "
              f"{stats['p99_us']:>9.1f}")

    print("\n--- Correctness Verification ---\n")

    # Verify Viterbi matches exhaustive search for small inputs
    for latin_input, _ in test_inputs:
        lattice = build_lattice(latin_input)
        viterbi_results = viterbi_top_k(latin_input, lattice, k=10)
        exhaustive_results = exhaustive_search(latin_input, lattice, k=10)

        if not viterbi_results and not exhaustive_results:
            print(f"  '{latin_input}': Both algorithms: no paths (OK)")
            continue

        # Compare top result
        v_top = viterbi_results[0].thai_text if viterbi_results else "(none)"
        e_top = exhaustive_results[0].thai_text if exhaustive_results else "(none)"
        match = "✓" if v_top == e_top else "✗"

        v_score = viterbi_results[0].score if viterbi_results else float("inf")
        e_score = exhaustive_results[0].score if exhaustive_results else float("inf")

        print(f"  '{latin_input}': Viterbi={v_top} ({v_score:.3f}), "
              f"Exhaustive={e_top} ({e_score:.3f}) [{match}]")

    print("\nDone.")


if __name__ == "__main__":
    main()
