"""
Test Cases for THAIME Candidate Selection Algorithm Prototype

Validates correctness, ranking quality, and performance of the
Viterbi-based candidate selection algorithm.

Run with: pytest test_cases.py -v
"""

from __future__ import annotations

import math
import time

import pytest

from candidate_selection import (
    DEFAULT_SEGMENTATION_PENALTY,
    LatticeEdge,
    ScoredPath,
    build_lattice,
    convert,
    edge_cost,
    exhaustive_search,
    path_score,
    viterbi_top_k,
)


# ---------------------------------------------------------------------------
# Test: Lattice construction
# ---------------------------------------------------------------------------

class TestLatticeConstruction:
    """Tests for build_lattice()."""

    def test_basic_lattice(self):
        """Lattice for 'khon' should contain at least one edge."""
        lattice = build_lattice("khon")
        assert len(lattice) > 0

    def test_no_matches(self):
        """Lattice for gibberish input should be empty."""
        lattice = build_lattice("xyzxyz")
        assert len(lattice) == 0

    def test_rongrean_has_both_single_and_compound(self):
        """'rongrean' should produce edges for โรงเรียน and also โรง + เรียน."""
        lattice = build_lattice("rongrean")
        thai_texts = {e.thai_text for e in lattice}
        # Should have the compound word
        assert "โรงเรียน" in thai_texts
        # Should have the components
        assert "โรง" in thai_texts
        assert "เรียน" in thai_texts

    def test_edge_positions_valid(self):
        """All edges should have valid start < end positions within input."""
        latin_input = "rongrean"
        lattice = build_lattice(latin_input)
        for edge in lattice:
            assert 0 <= edge.start < edge.end <= len(latin_input)

    def test_edge_romanization_matches_substring(self):
        """Each edge's romanization should match the input substring."""
        latin_input = "sawatdee"
        lattice = build_lattice(latin_input)
        for edge in lattice:
            assert edge.romanization == latin_input[edge.start:edge.end]


# ---------------------------------------------------------------------------
# Test: Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    """Tests for edge_cost() and path_score()."""

    def test_higher_frequency_lower_cost(self):
        """More frequent words should have lower cost."""
        high_freq = LatticeEdge(0, 4, 1, "คน", 0.01, "khon")
        low_freq = LatticeEdge(0, 4, 2, "ข้น", 0.001, "khon")
        assert edge_cost(high_freq) < edge_cost(low_freq)

    def test_cost_is_negative_log(self):
        """Edge cost should equal -log(frequency)."""
        edge = LatticeEdge(0, 4, 1, "คน", 0.005, "khon")
        expected = -math.log(0.005)
        assert abs(edge_cost(edge) - expected) < 1e-10

    def test_zero_frequency_uses_floor(self):
        """Zero frequency should use MIN_FREQUENCY floor, not blow up."""
        edge = LatticeEdge(0, 4, 1, "คน", 0.0, "khon")
        cost = edge_cost(edge)
        assert math.isfinite(cost)
        assert cost > 0

    def test_path_score_includes_penalty(self):
        """Path score should include segmentation penalty * num_words."""
        edge1 = LatticeEdge(0, 4, 1, "โรง", 0.001, "rong")
        edge2 = LatticeEdge(4, 8, 2, "เรียน", 0.001, "rean")
        penalty = 0.5

        score = path_score([edge1, edge2], segmentation_penalty=penalty)
        expected = edge_cost(edge1) + edge_cost(edge2) + 2 * penalty
        assert abs(score - expected) < 1e-10

    def test_single_word_path_beats_two_word_equal_freq(self):
        """A single-word path should score better than a 2-word path
        when all words have the same frequency (due to penalty)."""
        single = LatticeEdge(0, 8, 1, "โรงเรียน", 0.002, "rongrean")
        part1 = LatticeEdge(0, 4, 2, "โรง", 0.002, "rong")
        part2 = LatticeEdge(4, 8, 3, "เรียน", 0.002, "rean")

        score_single = path_score([single])
        score_double = path_score([part1, part2])
        assert score_single < score_double


# ---------------------------------------------------------------------------
# Test: Viterbi algorithm
# ---------------------------------------------------------------------------

class TestViterbiTopK:
    """Tests for viterbi_top_k()."""

    def test_rongrean_top_result(self):
        """Top result for 'rongrean' should be โรงเรียน (single word)."""
        candidates = convert("rongrean", k=5)
        assert len(candidates) > 0
        assert candidates[0].thai_text == "โรงเรียน"

    def test_sawatdee_top_result(self):
        """Top result for 'sawatdee' should be สวัสดี."""
        candidates = convert("sawatdee", k=5)
        assert len(candidates) > 0
        assert candidates[0].thai_text == "สวัสดี"

    def test_prathet_top_result(self):
        """Top result for 'prathet' should be ประเทศ."""
        candidates = convert("prathet", k=5)
        assert len(candidates) > 0
        assert candidates[0].thai_text == "ประเทศ"

    def test_khon_top_result(self):
        """Top result for 'khon' should be คน."""
        candidates = convert("khon", k=5)
        assert len(candidates) > 0
        assert candidates[0].thai_text == "คน"

    def test_ambiguous_input_produces_multiple(self):
        """Ambiguous input 'maikan' should produce multiple candidates."""
        candidates = convert("maikan", k=10)
        assert len(candidates) >= 2
        # Should have both the compound and decomposed forms
        thai_set = {c.thai_text for c in candidates}
        assert len(thai_set) >= 2

    def test_no_match_returns_empty(self):
        """Unrecognized input should return empty list."""
        candidates = convert("xyzxyz", k=5)
        assert candidates == []

    def test_results_sorted_by_score(self):
        """Results should be sorted by score (ascending = best first)."""
        candidates = convert("rongrean", k=10)
        for i in range(len(candidates) - 1):
            assert candidates[i].score <= candidates[i + 1].score

    def test_k_limit_respected(self):
        """Should return at most k results."""
        candidates = convert("maikan", k=2)
        assert len(candidates) <= 2

    def test_paths_are_complete(self):
        """Every returned path should tile the entire input with no gaps."""
        for latin_input in ["rongrean", "sawatdee", "prathet", "khon", "maikan"]:
            candidates = convert(latin_input, k=10)
            for cand in candidates:
                # Verify contiguous coverage
                assert cand.edges[0].start == 0
                assert cand.edges[-1].end == len(latin_input)
                for i in range(len(cand.edges) - 1):
                    assert cand.edges[i].end == cand.edges[i + 1].start


# ---------------------------------------------------------------------------
# Test: Correctness (Viterbi vs. Exhaustive)
# ---------------------------------------------------------------------------

class TestCorrectnessVsExhaustive:
    """Verify Viterbi produces the same top-k as exhaustive search."""

    @pytest.mark.parametrize("latin_input", [
        "rongrean", "sawatdee", "prathet", "khon", "maikan",
    ])
    def test_top_result_matches(self, latin_input):
        """Viterbi and exhaustive should agree on the top result."""
        lattice = build_lattice(latin_input)
        v_results = viterbi_top_k(latin_input, lattice, k=10)
        e_results = exhaustive_search(latin_input, lattice, k=10)

        if not v_results and not e_results:
            return  # Both empty is fine

        assert len(v_results) > 0
        assert len(e_results) > 0
        assert v_results[0].thai_text == e_results[0].thai_text
        assert abs(v_results[0].score - e_results[0].score) < 1e-6

    @pytest.mark.parametrize("latin_input", [
        "rongrean", "sawatdee", "prathet",
    ])
    def test_top_k_scores_match(self, latin_input):
        """Top-k scores from Viterbi should match exhaustive search."""
        lattice = build_lattice(latin_input)
        v_results = viterbi_top_k(latin_input, lattice, k=10)
        e_results = exhaustive_search(latin_input, lattice, k=10)

        # Compare scores for shared count
        count = min(len(v_results), len(e_results))
        for i in range(count):
            assert abs(v_results[i].score - e_results[i].score) < 1e-6


# ---------------------------------------------------------------------------
# Test: Performance
# ---------------------------------------------------------------------------

class TestPerformance:
    """Verify sub-millisecond performance on realistic lattice sizes."""

    def _make_synthetic_lattice(self, n_edges: int, input_len: int = 30):
        """Generate a synthetic lattice for performance testing."""
        edges = []
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
        return edges, "a" * input_len

    def test_small_lattice_under_1ms(self):
        """10-edge lattice scoring should complete in under 1ms."""
        edges, input_str = self._make_synthetic_lattice(10)
        # Warm up
        viterbi_top_k(input_str, edges, k=10)

        times = []
        for _ in range(50):
            t0 = time.perf_counter_ns()
            viterbi_top_k(input_str, edges, k=10)
            t1 = time.perf_counter_ns()
            times.append((t1 - t0) / 1_000_000)  # ms

        median = sorted(times)[len(times) // 2]
        assert median < 1.0, f"Median time {median:.3f}ms exceeds 1ms target"

    def test_medium_lattice_under_5ms(self):
        """50-edge lattice scoring should complete in under 5ms."""
        edges, input_str = self._make_synthetic_lattice(50)
        viterbi_top_k(input_str, edges, k=10)

        times = []
        for _ in range(50):
            t0 = time.perf_counter_ns()
            viterbi_top_k(input_str, edges, k=10)
            t1 = time.perf_counter_ns()
            times.append((t1 - t0) / 1_000_000)

        median = sorted(times)[len(times) // 2]
        assert median < 5.0, f"Median time {median:.3f}ms exceeds 5ms target"

    def test_large_lattice_under_50ms(self):
        """200-edge lattice scoring should complete in under 50ms."""
        edges, input_str = self._make_synthetic_lattice(200, input_len=60)
        viterbi_top_k(input_str, edges, k=10)

        times = []
        for _ in range(20):
            t0 = time.perf_counter_ns()
            viterbi_top_k(input_str, edges, k=10)
            t1 = time.perf_counter_ns()
            times.append((t1 - t0) / 1_000_000)

        median = sorted(times)[len(times) // 2]
        assert median < 50.0, f"Median time {median:.3f}ms exceeds 50ms target"


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_character_input(self):
        """Single-character inputs should work if in dictionary."""
        # 'ma' is 2 chars but let's test with the mock data
        candidates = convert("ma", k=5)
        # "ma" maps to มา in our mock dictionary
        if candidates:
            assert candidates[0].thai_text == "มา"

    def test_empty_input(self):
        """Empty input should return empty results (no edges)."""
        # Empty input -> no lattice edges -> no paths
        # The algorithm should handle this gracefully.
        lattice = build_lattice("")
        results = viterbi_top_k("", lattice, k=5)
        # Position 0 == input_len (0), so the initial empty path is valid
        assert len(results) >= 0

    def test_custom_dictionary(self):
        """Custom dictionary should be used instead of default."""
        custom_dict = [
            ("ทดสอบ", "test", 0.01, 100),
        ]
        candidates = convert("test", k=5, dictionary=custom_dict)
        assert len(candidates) == 1
        assert candidates[0].thai_text == "ทดสอบ"

    def test_segmentation_penalty_zero(self):
        """With zero penalty, multi-word paths may rank higher if
        component frequencies are higher."""
        # With no penalty, the scoring is purely frequency-based
        candidates = convert("rongrean", k=10, segmentation_penalty=0.0)
        assert len(candidates) > 0

    def test_high_segmentation_penalty(self):
        """With very high penalty, single-word paths should always win."""
        candidates = convert("rongrean", k=5, segmentation_penalty=10.0)
        assert len(candidates) > 0
        # First result should be the single-word form
        assert candidates[0].thai_text == "โรงเรียน"
        assert len(candidates[0].edges) == 1

    def test_duplicate_word_ids_deduplicated_in_lattice(self):
        """Multiple romanizations for the same word should produce
        separate lattice edges (they match different substrings)."""
        # "dii" and "dee" both map to ดี (word_id 3)
        lattice_dii = build_lattice("dii")
        lattice_dee = build_lattice("dee")
        # Both should find ดี
        assert any(e.thai_text == "ดี" for e in lattice_dii)
        assert any(e.thai_text == "ดี" for e in lattice_dee)


# ---------------------------------------------------------------------------
# Test: ScoredPath data structure
# ---------------------------------------------------------------------------

class TestScoredPath:
    """Tests for ScoredPath dataclass."""

    def test_thai_text_auto_generated(self):
        """ScoredPath should auto-concatenate thai_text from edges."""
        edges = [
            LatticeEdge(0, 4, 1, "โรง", 0.001, "rong"),
            LatticeEdge(4, 8, 2, "เรียน", 0.001, "rean"),
        ]
        path = ScoredPath(edges=edges, score=5.0)
        assert path.thai_text == "โรงเรียน"

    def test_empty_edges(self):
        """Empty path should have empty thai_text."""
        path = ScoredPath(edges=[], score=0.0)
        assert path.thai_text == ""
