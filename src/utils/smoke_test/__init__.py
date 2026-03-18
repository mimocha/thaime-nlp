"""Smoke test harness for release validation.

Loads pipeline artifacts (trie dataset + ngram binary) and validates
known-answer test cases through the full lookup → score → viterbi pipeline.

Usage:
    python -m pipelines smoke-test
    python -m pipelines smoke-test --data-dir pipelines/outputs --beam-width 10
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.utils.smoke_test.ngram_score import NgramModel, load_ngram_binary
from src.utils.smoke_test.trie_lookup import TrieData, load_trie
from src.utils.smoke_test.viterbi import beam_search

# Default test cases file (relative to this module)
DEFAULT_TEST_CASES = Path(__file__).parent / "test_cases.yaml"


@dataclass
class TestResult:
    """Result of a single test case."""

    input: str
    expected: str
    note: str
    status: str  # "pass", "warn", "fail"
    rank: int | None  # 1-indexed rank, or None if not found
    top_result: str | None  # The actual rank-1 result
    top_score: float | None  # Score of top result


def load_test_cases(path: Path | None = None) -> list[dict]:
    """Load test cases from YAML file.

    Args:
        path: Path to test_cases.yaml. Defaults to bundled file.

    Returns:
        List of dicts with 'input', 'expected', and optional 'note' keys.
    """
    if path is None:
        path = DEFAULT_TEST_CASES

    with open(path, encoding="utf-8") as f:
        cases = yaml.safe_load(f)

    return cases


def find_ngram_binary(data_dir: Path) -> Path:
    """Find the ngram binary file in the data directory.

    Looks for files matching thaime_ngram_v*_mc*.bin and returns the first match.

    Raises:
        FileNotFoundError: If no binary file is found.
    """
    ngram_dir = data_dir / "ngram"
    bins = sorted(ngram_dir.glob("thaime_ngram_v*_mc*.bin"))
    if not bins:
        raise FileNotFoundError(
            f"No ngram binary found in {ngram_dir}. "
            "Run 'python -m pipelines ngram encode' first."
        )
    # Return the most recently modified one
    return max(bins, key=lambda p: p.stat().st_mtime)


def run_smoke_tests(
    data_dir: Path,
    test_cases_path: Path | None = None,
    beam_width: int = 10,
) -> list[TestResult]:
    """Run all smoke test cases against pipeline artifacts.

    Args:
        data_dir: Path to pipelines/outputs/ directory.
        test_cases_path: Path to test_cases.yaml. Defaults to bundled file.
        beam_width: Beam width for Viterbi search.

    Returns:
        List of TestResult for each test case.
    """
    # Load artifacts
    trie_path = data_dir / "trie" / "trie_dataset.json"
    if not trie_path.exists():
        raise FileNotFoundError(
            f"Trie dataset not found at {trie_path}. "
            "Run 'python -m pipelines trie run' first."
        )

    ngram_path = find_ngram_binary(data_dir)

    trie = load_trie(trie_path)
    model = load_ngram_binary(ngram_path)

    # Load test cases
    cases = load_test_cases(test_cases_path)

    # Run each test case
    results: list[TestResult] = []
    for case in cases:
        input_text = case["input"]
        expected = case["expected"]
        note = case.get("note", "")

        # Strip spaces from input (the engine concatenates keystrokes)
        clean_input = input_text.replace(" ", "")

        # Run beam search
        candidates = beam_search(clean_input, trie, model, beam_width=beam_width)

        # Check results
        top_result = candidates[0][0] if candidates else None
        top_score = candidates[0][1] if candidates else None

        rank = None
        for i, (output, _score) in enumerate(candidates):
            if output == expected:
                rank = i + 1
                break

        if rank == 1:
            status = "pass"
        elif rank is not None:
            status = "warn"
        else:
            status = "fail"

        results.append(
            TestResult(
                input=input_text,
                expected=expected,
                note=note,
                status=status,
                rank=rank,
                top_result=top_result,
                top_score=top_score,
            )
        )

    return results
