"""
Evaluation Script for Frequency Scoring Formulas

Runs all scoring formulas (from scoring.py) against all test sets
(A, B, C) with a sweep of segmentation-penalty (λ) values.

Usage:
    cd /home/runner/work/thaime-nlp/thaime-nlp
    python experiments/006-frequency-scoring/evaluate.py

Outputs:
    - Console table of metrics per formula × λ
    - experiments/006-frequency-scoring/results_raw.json

Author: THAIME Research
Date: 2025-07-14
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Resolve experiment directory relative to this script
EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from scoring import SCORING_FORMULAS, MIN_FREQ, load_trie_dataset

# ---------------------------------------------------------------------------
# Data structures (matching R005)
# ---------------------------------------------------------------------------

@dataclass
class LatticeEdge:
    """A single edge in the word lattice."""
    start: int
    end: int
    word_id: int
    thai_text: str
    frequency: float
    romanization: str


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
# Romanization index
# ---------------------------------------------------------------------------

def build_romanization_index(
    word_data: dict[int, dict],
) -> dict[str, list[tuple[str, float, int]]]:
    """Build romanization_key → [(thai, frequency, word_id), ...] from word data."""
    index: dict[str, list[tuple[str, float, int]]] = {}
    for wid, wd in word_data.items():
        for rom in wd["romanizations"]:
            if rom not in index:
                index[rom] = []
            index[rom].append((wd["thai"], wd["frequency"], wid))
    return index


# ---------------------------------------------------------------------------
# Lattice construction
# ---------------------------------------------------------------------------

def build_lattice(
    latin_input: str,
    rom_index: dict[str, list[tuple[str, float, int]]],
) -> list[LatticeEdge]:
    """Build a word lattice via common prefix search on the input string."""
    edges: list[LatticeEdge] = []
    input_len = len(latin_input)
    for start in range(input_len):
        for end in range(start + 1, input_len + 1):
            substring = latin_input[start:end]
            if substring in rom_index:
                for thai_text, freq, word_id in rom_index[substring]:
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
# Pluggable Viterbi
# ---------------------------------------------------------------------------

CostFn = type(lambda: None)  # callable type hint shorthand


def viterbi_top_k(
    latin_input: str,
    lattice: list[LatticeEdge],
    k: int,
    segmentation_penalty: float,
    cost_fn,
    word_data_lookup: dict[int, dict],
) -> list[ScoredPath]:
    """Find the top-k best paths using modified Viterbi with pluggable cost.

    Instead of the fixed -log(freq) edge cost from R005, this version
    delegates edge costing to *cost_fn(word_id, word_data_dict)*.
    """
    input_len = len(latin_input)

    edges_from: dict[int, list[LatticeEdge]] = {}
    for edge in lattice:
        if edge.start not in edges_from:
            edges_from[edge.start] = []
        edges_from[edge.start].append(edge)

    # best_paths_at[pos] = list of (score, edge_list)
    best_paths_at: dict[int, list[tuple[float, list[LatticeEdge]]]] = {
        0: [(0.0, [])],
    }

    for pos in range(input_len):
        if pos not in best_paths_at or pos not in edges_from:
            continue

        for edge in edges_from[pos]:
            wd = word_data_lookup.get(edge.word_id)
            if wd is not None:
                edge_cost = cost_fn(edge.word_id, wd)
            else:
                # Fallback if word_id not in lookup
                freq = max(edge.frequency, MIN_FREQ)
                edge_cost = -math.log(freq)

            cost = edge_cost + segmentation_penalty

            for prev_score, prev_path in best_paths_at[pos]:
                new_score = prev_score + cost
                new_path = prev_path + [edge]
                end = edge.end

                if end not in best_paths_at:
                    best_paths_at[end] = []
                best_paths_at[end].append((new_score, new_path))

                # Prune to k-best at each position
                if len(best_paths_at[end]) > k:
                    best_paths_at[end].sort(key=lambda x: x[0])
                    best_paths_at[end] = best_paths_at[end][:k]

    if input_len not in best_paths_at:
        return []

    results = best_paths_at[input_len]
    results.sort(key=lambda x: x[0])
    return [
        ScoredPath(edges=path, score=score)
        for score, path in results[:k]
    ]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def reciprocal_rank(expected: str, candidates: list[str]) -> float:
    """1/rank of the expected string in candidates, or 0 if absent."""
    for i, c in enumerate(candidates):
        if c == expected:
            return 1.0 / (i + 1)
    return 0.0


def find_rank(expected: str, candidates: list[str]) -> int:
    """1-based rank of expected in candidates, or 0 if absent."""
    for i, c in enumerate(candidates):
        if c == expected:
            return i + 1
    return 0


# ---------------------------------------------------------------------------
# Per-test-set evaluation
# ---------------------------------------------------------------------------

def evaluate_set_a(
    test_set: list[dict],
    rom_index: dict,
    word_data: dict,
    cost_fn,
    lam: float,
    k: int = 10,
) -> tuple[float, float, list[dict]]:
    """Evaluate Set A: single-word common words. Returns (mrr, top1, details)."""
    rr_sum = 0.0
    top1_hits = 0
    details = []

    for entry in test_set:
        inp = entry["romanization_input"]
        expected = entry["expected_thai"]

        lattice = build_lattice(inp, rom_index)
        paths = viterbi_top_k(inp, lattice, k, lam, cost_fn, word_data)
        top_texts = []
        seen = set()
        for p in paths:
            if p.thai_text not in seen:
                top_texts.append(p.thai_text)
                seen.add(p.thai_text)

        rr = reciprocal_rank(expected, top_texts)
        rr_sum += rr
        if top_texts and top_texts[0] == expected:
            top1_hits += 1

        details.append({
            "input": inp,
            "expected": expected,
            "rank": find_rank(expected, top_texts),
            "top_10": top_texts[:10],
        })

    n = len(test_set)
    return rr_sum / n if n else 0.0, top1_hits / n if n else 0.0, details


def evaluate_set_b(
    test_set: list[dict],
    rom_index: dict,
    word_data: dict,
    cost_fn,
    lam: float,
    k: int = 10,
) -> tuple[float, float, list[dict]]:
    """Evaluate Set B: ambiguous inputs. Returns (mrr, top1, details)."""
    rr_sum = 0.0
    top1_hits = 0
    details = []

    for entry in test_set:
        inp = entry["romanization_input"]
        expected = entry["expected_top_candidate"]

        lattice = build_lattice(inp, rom_index)
        paths = viterbi_top_k(inp, lattice, k, lam, cost_fn, word_data)
        top_texts = []
        seen = set()
        for p in paths:
            if p.thai_text not in seen:
                top_texts.append(p.thai_text)
                seen.add(p.thai_text)

        rr = reciprocal_rank(expected, top_texts)
        rr_sum += rr
        if top_texts and top_texts[0] == expected:
            top1_hits += 1

        details.append({
            "input": inp,
            "expected": expected,
            "rank": find_rank(expected, top_texts),
            "top_10": top_texts[:10],
        })

    n = len(test_set)
    return rr_sum / n if n else 0.0, top1_hits / n if n else 0.0, details


def evaluate_set_c(
    test_set: list[dict],
    rom_index: dict,
    word_data: dict,
    cost_fn,
    lam: float,
    k: int = 10,
) -> tuple[float, list[dict]]:
    """Evaluate Set C: override recall. Returns (recall@10, details).

    For each override word in the trie, try each override romanization.
    If any romanization produces the word in top-10 candidates, count as hit.
    """
    hits = 0
    eligible = 0
    details = []

    for entry in test_set:
        if not entry.get("in_trie"):
            continue

        target_thai = entry["thai"]
        romanizations = entry["override_romanizations"]
        eligible += 1
        found = False
        found_via = None

        for rom in romanizations:
            lattice = build_lattice(rom, rom_index)
            paths = viterbi_top_k(rom, lattice, k, lam, cost_fn, word_data)
            top_texts = []
            seen = set()
            for p in paths:
                if p.thai_text not in seen:
                    top_texts.append(p.thai_text)
                    seen.add(p.thai_text)

            if target_thai in top_texts[:10]:
                found = True
                found_via = rom
                break

        if found:
            hits += 1

        details.append({
            "thai": target_thai,
            "found": found,
            "found_via": found_via,
            "romanizations_tried": len(romanizations),
        })

    recall = hits / eligible if eligible else 0.0
    return recall, details


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def load_test_set(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Test sets have entries under either "entries" or "test_cases" key,
    # or the file itself may be a list
    if isinstance(data, list):
        return data
    for key in ("entries", "test_cases"):
        if key in data:
            return data[key]
    return data


def main():
    print("=" * 90)
    print("THAIME Frequency Scoring — Evaluation")
    print("=" * 90)

    # --- Load data ---
    trie_path = EXPERIMENT_DIR / "reference" / "trie_dataset_sample_5k.json"
    print(f"\nLoading trie dataset from {trie_path.name} ...")
    dataset = load_trie_dataset(trie_path)
    word_data = dataset["word_data"]
    print(f"  Loaded {len(word_data)} words")

    print("Building romanization index ...")
    rom_index = build_romanization_index(word_data)
    print(f"  {len(rom_index)} unique romanization keys")

    # Load test sets
    set_a = load_test_set(EXPERIMENT_DIR / "test_set_a.json")
    set_b = load_test_set(EXPERIMENT_DIR / "test_set_b.json")
    set_c = load_test_set(EXPERIMENT_DIR / "test_set_c.json")
    print(f"  Test sets: A={len(set_a)}, B={len(set_b)}, C={len(set_c)}")

    # --- Configuration ---
    lambda_values = [0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
    formula_names = list(SCORING_FORMULAS.keys())

    total_combos = len(formula_names) * len(lambda_values)
    print(f"\nRunning {len(formula_names)} formulas × {len(lambda_values)} λ values = {total_combos} combinations\n")

    # --- Header ---
    header = (
        f"{'Formula':<18} | {'λ':>4} | {'A MRR':>7} | {'A Top1':>7} | "
        f"{'B MRR':>7} | {'B Top1':>7} | {'C Rec':>7}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    all_results = []
    combo_idx = 0

    for fname in formula_names:
        cost_fn = SCORING_FORMULAS[fname]

        for lam in lambda_values:
            combo_idx += 1
            t0 = time.time()

            a_mrr, a_top1, a_details = evaluate_set_a(
                set_a, rom_index, word_data, cost_fn, lam,
            )
            b_mrr, b_top1, b_details = evaluate_set_b(
                set_b, rom_index, word_data, cost_fn, lam,
            )
            c_recall, c_details = evaluate_set_c(
                set_c, rom_index, word_data, cost_fn, lam,
            )

            elapsed = time.time() - t0

            row = (
                f"{fname:<18} | {lam:>4.1f} | {a_mrr:>7.3f} | {a_top1:>7.3f} | "
                f"{b_mrr:>7.3f} | {b_top1:>7.3f} | {c_recall:>7.3f}"
            )
            print(f"{row}  ({elapsed:.1f}s) [{combo_idx}/{total_combos}]")

            all_results.append({
                "formula": fname,
                "lambda": lam,
                "set_a_mrr": round(a_mrr, 4),
                "set_a_top1": round(a_top1, 4),
                "set_b_mrr": round(b_mrr, 4),
                "set_b_top1": round(b_top1, 4),
                "set_c_recall": round(c_recall, 4),
                "set_a_details": a_details,
                "set_b_details": b_details,
                "set_c_details": c_details,
            })

    print(sep)

    # --- Save results ---
    output_path = EXPERIMENT_DIR / "results_raw.json"
    output = {
        "metadata": {
            "date": str(date.today()),
            "trie_dataset": "trie_dataset_sample_5k.json",
            "lambda_values": lambda_values,
            "formulas": formula_names,
            "test_set_sizes": {
                "set_a": len(set_a),
                "set_b": len(set_b),
                "set_c": len(set_c),
            },
        },
        "results": all_results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()
