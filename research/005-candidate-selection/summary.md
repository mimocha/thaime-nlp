# Candidate Selection Algorithm for THAIME

**Date:** 2026-03-09
**Author:** Claude (agent) + Chawit Leosrisook (maintainer)
**Branch:** `research/005-candidate-selection`
**Status:** Complete

## Research Question

Given a word lattice from trie prefix search, what algorithm and scoring model should THAIME use to find and rank Thai word/phrase candidates for the MVP CLI demo?

## Approach

We evaluated candidate selection algorithms through three complementary methods:

1. **Literature survey** — Documented how four production IME systems (Google Mozc, librime/RIME, libkkc, Anthy) solve the same problem: scoring and ranking paths through a word lattice.
2. **Algorithm evaluation** — Compared four algorithmic approaches (Viterbi DP, beam search, exhaustive enumeration, DFS with memoization) on correctness, complexity, top-k support, upgrade path, and implementation effort.
3. **Python prototype** — Built a working prototype with a mock dictionary, validated on five test inputs, and confirmed sub-millisecond performance on realistic lattice sizes up to 200 edges.

## Key Findings

### 1. All surveyed IMEs use Viterbi on a word lattice — this is the established approach

Every production IME we surveyed (Mozc, librime, libkkc, Anthy) uses the same core architecture: build a word lattice from dictionary lookup, assign costs to edges using a language model, and find the lowest-cost path using the Viterbi algorithm (dynamic programming on a DAG). This architecture dates back to the 1980s and has been refined for decades. There is no reason for THAIME to deviate from it.

### 2. Unigram scoring with a segmentation penalty is sufficient for the MVP

For the MVP, a simple scoring model works well:

```
Score(path) = Σ(-log(freq_i)) + N × penalty
```

Where `freq_i` is the corpus frequency of word `i` in the path, `N` is the number of words, and `penalty` is a constant that discourages over-segmentation. In prototype testing with `penalty = 0.5`, this formula correctly ranks single-word interpretations above multi-word decompositions for all five test inputs (e.g., โรงเรียน ranks above โรง+เรียน).

### 3. Modified Viterbi with k-best tracking is the recommended algorithm

The standard Viterbi algorithm finds only the single best path. For an IME, we need top-k candidates. The recommended approach maintains the k-best partial paths at each lattice position (rather than just the single best). This has O(|E| × k) time complexity and naturally produces ranked results. The prototype confirms this works correctly and matches exhaustive search results.

### 4. Performance is well within the sub-millisecond target

Python prototype measurements on synthetic lattices:

| Lattice Size | Input Length | Mean (µs) | Median (µs) | P99 (µs) |
|-------------|-------------|-----------|-------------|----------|
| 10 edges    | 30 chars    | 9.3       | 8.9         | 38.8     |
| 25 edges    | 30 chars    | 15.0      | 11.4        | 45.1     |
| 50 edges    | 30 chars    | 211.3     | 209.0       | 238.6    |
| 100 edges   | 33 chars    | 713.6     | 709.6       | 976.3    |
| 200 edges   | 66 chars    | 696.1     | 696.8       | 734.7    |

Even the 200-edge case (far larger than typical IME input) completes under 1ms in Python. A Rust implementation should be 10–100× faster, placing realistic inputs firmly in the single-digit microsecond range.

### 5. The segmentation penalty is the key tuning parameter

The penalty value controls the trade-off between preferring longer words (fewer segments) and allowing valid multi-word interpretations. At `penalty = 0.5`:
- โรงเรียน (1 word, score=6.49) beats โรง+เรียน (2 words, score=13.82)
- ไม้กั้น (1 word, score=8.61) beats ไม่+กัน (2 words, score=11.11)

The penalty should be tunable at runtime. Starting value of 0.5 works well for the mock dictionary but may need adjustment once real frequency data from CP05 is available.

## Literature Survey

### Reference IME Comparison

| System | Algorithm | Language Model | Lattice Representation | Candidates Shown | Context Used |
|--------|-----------|---------------|----------------------|-----------------|-------------|
| **Google Mozc** | Viterbi (shortest path DP) | Unigram + bigram costs on nodes/edges; user history; rewriter modules | Directed graph with nodes per word candidate, edges for transitions | Multiple (user selectable) | Yes — session state, user history predictor, rewriter pipeline |
| **librime (RIME)** | Viterbi / lattice decoder | N-gram LM (configurable); fuzzy match scoring; user learning | Segment graph + lattice of candidate expansions | Top-N ranked list | Yes — user dictionary, learned preferences, schema-based config |
| **libkkc** | Viterbi (N-best) | N-gram (bigram/trigram trained on corpus) | Lattice with kana segments mapped to kanji candidates | N-best candidates | Limited — primarily LM context within current input |
| **Anthy** | Viterbi (path search) | Statistical LM (bigram/trigram since 2005); max-entropy model (2006) | Lattice from dictionary segmentation with feature scoring | Best path + alternatives | Yes — POS features, morphological features, discriminative scoring |

### Key Observations from the Survey

1. **Viterbi is universal.** All four systems use Viterbi or equivalent DP for path search. No production IME uses beam search or exhaustive enumeration for the core conversion.

2. **Unigram-only is a valid starting point.** Mozc's converter supports unigram-only scoring as a fallback when bigram data is unavailable. This validates our MVP approach.

3. **Bigram scoring is the standard upgrade.** All four systems incorporate at least bigram transition costs. This is the clear next step after MVP.

4. **Post-processing matters.** Mozc's rewriter pipeline (which re-ranks and transforms candidates after Viterbi) is responsible for much of its conversion quality. This is a medium-term concern, not MVP.

5. **User learning is standard.** All systems track user selections to boost frequently chosen candidates. This is a post-MVP feature for THAIME.

## Algorithm Evaluation

### Options Compared

| Criterion | A: Viterbi DP | B: Beam Search | C: Exhaustive + Pruning | D: DFS + Memoization |
|-----------|:------------:|:--------------:|:----------------------:|:-------------------:|
| **Correctness** | Exact (globally optimal) | Approximate (may miss best) | Exact | Exact |
| **Time complexity** | O(\|E\| × k) | O(\|E\| × B) | O(exponential, pruned) | O(\|E\| × k) |
| **Space complexity** | O(n × k) | O(n × B) | O(paths found) | O(n × k + stack) |
| **Top-k support** | Natural (k-best extension) | Natural (beam = candidates) | Natural (enumerate all) | Natural (k-best at each pos) |
| **Bigram upgrade** | Trivial (change edge weights) | Trivial | Trivial | Trivial |
| **Implementation** | ~100 lines | ~80 lines | ~50 lines | ~80 lines |
| **Production proven** | Mozc, librime, libkkc, Anthy | Neural IMEs, MT decoders | None (toy only) | Equivalent to Viterbi |

### Recommendation: Option A (Viterbi DP with k-best tracking)

**Rationale:**

1. **Industry standard.** Every production IME surveyed uses Viterbi. Choosing the same approach means we can draw on extensive literature, reference implementations, and proven tuning strategies.

2. **Exact optimality.** Unlike beam search, Viterbi guarantees finding the globally optimal path. For an IME where conversion quality directly impacts user experience, this guarantee matters.

3. **Natural k-best extension.** Maintaining k-best paths at each position is a minor extension to standard Viterbi, adding only a constant factor (k) to complexity.

4. **Clean upgrade path.** Transitioning from unigram to bigram scoring requires only changing how edge costs are computed — the algorithm structure is identical.

5. **Iterative Viterbi preferred over recursive DFS.** Option D is mathematically equivalent to Option A but the iterative left-to-right scan is more cache-friendly and avoids stack overflow on long inputs. The iterative form is also what reference implementations use.

**Why not beam search:** Beam search is approximate and its quality depends on beam width tuning. For typical IME lattices (small by NLP standards), Viterbi is fast enough that there's no need for an approximate algorithm.

**Why not exhaustive enumeration:** Works for toy examples but has exponential worst-case complexity. Even with pruning, it's not predictable enough for a production IME that must respond within a latency budget on every keystroke.

## MVP Scoring Model

### Formula

```
Score(path) = Σᵢ cost(edgeᵢ) + N × λ

where:
  cost(edge) = -log(max(freq, ε))
  N          = number of edges (words) in the path
  λ          = segmentation penalty (default: 0.5)
  ε          = frequency floor (1×10⁻⁷)
  freq       = normalized corpus frequency for the word
```

Lower score is better (the algorithm minimizes total cost).

### Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `λ` (segmentation penalty) | 0.5 | Empirically tuned on prototype test cases. Sufficiently penalizes over-segmentation without suppressing valid multi-word paths. Should be runtime-configurable. |
| `ε` (frequency floor) | 1×10⁻⁷ | Prevents -log(0) = ∞ for out-of-vocabulary or zero-frequency words. Results in a cost of ~16.1, placing unknown words at the bottom of rankings. |
| `k` (top-k candidates) | 10 | Returns 10 candidates to the UI. Typical for IME candidate windows (5–10 visible at a time). |

### Scoring Model Rationale

1. **Negative log-frequency** transforms multiplicative probabilities into additive costs, enabling efficient DP accumulation and avoiding floating-point underflow.

2. **Segmentation penalty** addresses the core Thai IME challenge: Thai has no word boundaries, so the lattice often contains many valid segmentations. Without the penalty, short high-frequency words would dominate (e.g., every input would decompose into one-syllable words). The penalty provides a prior toward longer, more specific words.

3. **Frequency floor** handles graceful degradation: unknown words get a very high cost but can still appear in paths when no better alternative exists.

### Tie-breaking

When two paths have identical scores (rare in practice due to floating-point frequency values), the algorithm returns them in lattice construction order, which is left-to-right, longest-match-first. This naturally prefers earlier-matched, longer words — a sensible default.

### Partial Coverage

If no valid path tiles the entire input, the algorithm returns an empty candidate list. The engine should signal to the UI that conversion failed, prompting the user to edit their input. Partial match support (returning the longest prefix that can be segmented) is deferred to post-MVP.

## Prototype Results

### Test Case Outputs

| Input | Expected Top | Actual Top | Score | Rank | All Candidates |
|-------|-------------|-----------|-------|------|---------------|
| `rongrean` | โรงเรียน | โรงเรียน | 6.491 | #1 | โรงเรียน (6.49), โรง+เรียน (13.82) |
| `sawatdee` | สวัสดี | สวัสดี | 6.309 | #1 | สวัสดี (6.31), สวัส+ดี (14.48) |
| `prathet` | ประเทศ | ประเทศ | 6.155 | #1 | ประเทศ (6.16), ประ+เทศ (15.55) |
| `khon` | คน | คน | 5.268 | #1 | คน (5.27) |
| `maikan` | ไม้กั้น or ไม่+กัน | ไม้กั้น | 8.612 | #1 | ไม้กั้น (8.61), ไม่+กัน (11.11), ไม่+กั้น (13.54) |

All five test cases return the expected top result. The ambiguous case (`maikan`) correctly surfaces both interpretations, with the single-word form ranked higher due to the segmentation penalty.

### Correctness Verification

The Viterbi algorithm was cross-validated against an exhaustive DFS search on all five test inputs. Results match exactly (scores agree to 6 decimal places), confirming the DP implementation is correct.

### Performance Summary

All measurements in Python 3.12 on the prototype (pure Python, no C extensions). A Rust implementation would be significantly faster.

- **10 edges (typical short input):** 9 µs median — well under 1ms target
- **50 edges (medium input):** 209 µs median — under 1ms target
- **100 edges (long input):** 710 µs median — under 1ms target
- **200 edges (extreme case):** 697 µs median — under 1ms target

The sub-millisecond performance target is met even in pure Python for all realistic lattice sizes. In Rust, performance should be at least 10× better due to compiled code, cache-friendly data layout, and elimination of Python overhead.

### Test Suite

38 automated tests covering:
- Lattice construction (5 tests)
- Scoring formula (5 tests)
- Viterbi algorithm correctness (9 tests)
- Viterbi vs. exhaustive cross-validation (8 parametrized tests)
- Performance benchmarks (3 tests)
- Edge cases (6 tests)
- Data structure validation (2 tests)

All 38 tests pass.

## Upgrade Path

### Bigram Scoring

**What changes:** The edge cost function gains a transition component: `cost(edge_j | edge_i) = -log(P(word_j | word_i))` where `edge_i` is the preceding edge. The Viterbi state becomes `(position, previous_word_id)` instead of just `(position)`.

**What stays the same:** The overall algorithm structure (left-to-right DP with k-best tracking), the lattice construction, and the top-k extraction.

**Data needed:** A bigram frequency table `(word_i, word_j) → count` extracted from Thai corpora. At minimum, bigrams for the 50K most frequent words from the combined corpus (prachathai, wisesight, wongnai, thwiki). Smoothing (e.g., Kneser-Ney or simple add-α) is necessary for unseen bigrams.

**Estimated effort:** 2–3 days for the data pipeline (extract bigram counts from tokenized corpora), 1 day to modify the scoring algorithm.

### Context from Committed Text

**Interface:** The frontend passes the last N committed words (or their word IDs) to the scoring engine before each conversion request. The scoring engine uses these as the left context for bigram/trigram scoring of the first word in the lattice.

**What changes:** The Viterbi initialization step seeds the starting state with the committed context rather than a uniform prior.

**What stays the same:** Everything else — the lattice, the DP algorithm, the top-k extraction.

### Romanization Confidence Weights

If CP05 adds confidence weights to romanization variants (e.g., `rongrean: 0.9, rongrian: 0.7`), these factor into the edge cost as an additive term: `cost(edge) = -log(freq) - α × log(confidence)` where `α` is a mixing weight. This is a single-line change to the cost function.

### User Dictionary

User-added words should receive a frequency boost (e.g., set their frequency to the 90th percentile of the main dictionary, or use a dedicated user-frequency that decays over time). They participate in the lattice and scoring identically to main dictionary entries.

### Adaptive Learning

Track user selections: when the user picks candidate #3 instead of #1, increment a per-word counter. At scoring time, blend corpus frequency with user frequency: `freq_effective = (1-β) × freq_corpus + β × freq_user` where `β` increases with more user data. This requires persistent storage of user selection counts.

## Open Questions

1. **Optimal segmentation penalty value with real data.** The value 0.5 works for the mock dictionary but should be re-tuned once CP05 provides real frequency data. Consider making it configurable in the engine's config file.

2. **Frequency normalization.** CP05's merged frequency values need to be normalized to probabilities. The normalization method (simple division by total, or rank-based) may affect scoring quality.

3. **Handling of partial input.** The current algorithm requires the input to be completely tiled by lattice edges. For incremental (keystroke-by-keystroke) conversion, the engine may need to score partial paths and present intermediate candidates. This is an implementation concern for the engine, not a research question.

4. **Duplicate candidate suppression.** When multiple romanization variants map to the same Thai output (e.g., `rongrean` and `rongrian` both match โรงเรียน), the current algorithm may produce duplicate Thai candidates. The engine should deduplicate by Thai text, keeping only the best-scoring instance.

5. **Very long inputs.** For inputs exceeding 30–40 characters, the lattice may become large. The engine should impose a maximum input length or use beam pruning to cap lattice size. This is unlikely to be an issue for MVP usage patterns.

## References

### Project Documents
- THAIME Conversion Algorithm — project knowledge document (primary reference)
- THAIME 2026 Roadmap — project knowledge document
- Research 004: Trie Data Structure Selection — `research/004-trie-selection/summary.md`

### Reference IME Projects
- Google Mozc — https://github.com/google/mozc (BSD-3-Clause). Architecture documented at https://deepwiki.com/fcitx/mozc
- librime (RIME) — https://github.com/rime/librime (BSD-3-Clause). Architecture documented at https://deepwiki.com/rime/librime
- libkkc — https://github.com/ueno/libkkc. N-gram Viterbi kana-kanji converter.
- Anthy — https://github.com/fujiwarat/anthy-unicode. Lattice-based Japanese IME with statistical LM.
- libime (Fcitx5) — https://deepwiki.com/fcitx/libime/3-pinyin-input-method. Pinyin segmentation and lattice scoring.

### Academic and Technical References
- Viterbi, A. (1967). "Error bounds for convolutional codes and an asymptotically optimum decoding algorithm." IEEE Trans. Information Theory.
- SentencePiece unigram model — https://github.com/google/sentencepiece. Uses same -log(freq) + segmentation penalty scoring on a word lattice.
- Eppstein, D. (1998). "Finding the k shortest paths." SIAM J. Computing. For future reference on k-shortest path algorithms.
- kBestViterbi — https://github.com/carthach/kBestViterbi. Python reference for k-best Viterbi decoding.
- Hugging Face tokenizers — https://deepwiki.com/huggingface/tokenizers/4.3-unigram. Unigram lattice scoring documentation.
