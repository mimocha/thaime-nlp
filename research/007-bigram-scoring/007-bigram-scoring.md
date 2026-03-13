# N-gram Transition Probability for Candidate Ranking

**Topic:** research/007-bigram-scoring
**Date:** 2026-03-12
**Author:** Claude (agent) + Chawit Leosrisook (maintainer)
**Status:** Phase 3 Complete
**Prerequisites:** Research 005 (Candidate Selection), Research 006 (Frequency Scoring)

## Research Question

How should n-gram (starting with bigram) transition probabilities be extracted, smoothed, and integrated into THAIME's Viterbi scoring to improve context-dependent candidate ranking over the unigram baseline?

## Motivation

Research 006 established that unigram scoring (`-log(freq)`) achieves MRR=0.989 on common words and MRR=0.960 on ambiguous inputs — the practical ceiling for context-free scoring. The remaining ranking errors are genuine frequency ties that require context to disambiguate (e.g., "kao" -> ข้าว after กิน vs เขา otherwise).

Every production IME surveyed in Research 005 (Mozc, librime, libkkc, Anthy) uses at least bigram transition costs. This is the established next step for ranking improvement and a foundational component for THAIME's production engine.

## Background Summary

### Production IME Precedent

| IME | N-gram Order | Approach |
|-----|-------------|----------|
| Google Mozc | Bigram (POS-class) | ~500 POS classes, compact connection matrix |
| libkkc | Trigram (word) | Full word-level trigram |
| Anthy | Bigram (heuristic) | Class-based connectivity costs |
| SunPinyin | Trigram (with backoff) | Word-level trigram + backoff |
| libpinyin | Bigram (word) | Word-level bigram transition DB |
| RIME/librime | Configurable (default n=3) | Framework supports any n-gram order |

### Diminishing Returns by N-gram Order

From Jurafsky & Martin (SLP3), trained on 38M words:

| Model | Perplexity | Reduction over previous |
|-------|-----------|------------------------|
| Unigram | 962 | — |
| Bigram | 170 | **5.7x** |
| Trigram | 109 | **1.6x** |
| 4-gram+ | ~marginal | Not worth the cost |

The unigram-to-bigram jump is massive. Bigram-to-trigram is meaningful but much smaller. No production IME goes beyond trigram.

### Storage Estimates (50K vocab, moderate corpus)

| Model | Realistic entries | Approx. size |
|-------|------------------|--------------|
| Bigram | 1-5M | 10-50 MB |
| Trigram | 5-30M | 50-300 MB |

### Key References

- Kudo et al. 2011 — Efficient dictionary and LM compression for IME (ACL)
- Chen & Lee 2000 — Statistical approach to Chinese Pinyin input (ACL)
- Jurafsky & Martin — SLP3, Ch. 3: N-gram Language Models
- Chen & Goodman 1999 — An Empirical Study of Smoothing Techniques for Language Modeling (Modified Kneser-Ney)
- Brants et al. 2007 — Large Language Models in Machine Translation (Stupid Backoff)
- Research 005 — Candidate Selection Algorithm (Viterbi upgrade path section)
- Research 006 — Word Frequency Scoring (unigram ceiling finding)

## Scope

### In Scope

- Bigram extraction from Thai corpora (wisesight, wongnai, prachathai, thwiki)
- Smoothing method evaluation (add-alpha, Kneser-Ney, deleted interpolation)
- Bigram-aware Viterbi scoring prototype
- Creation of a ranking benchmark with context-dependent test cases
- Assessment of whether trigram provides meaningful improvement over bigram
- Concrete recommendation for the Rust engine

### Out of Scope

- 4-gram and higher (evidence shows negligible returns)
- User history / adaptive learning (post-MVP feature)
- Cross-sentence context (only within-input + last committed word)
- Re-tuning segmentation penalty lambda (separate study)
- POS-class-based n-grams (requires a Thai POS taxonomy; word-level is simpler for THAIME's vocabulary size)

### N-gram Generalization Strategy

The extraction pipeline and Viterbi integration will be designed to be n-gram-order-agnostic (parameterized by `n`). Bigrams (n=2) are the primary deliverable. If evaluation shows specific cases where bigram context is insufficient, the same pipeline can be rerun with n=3 as a follow-up within the same branch — no separate research topic needed.

## Experimental Variables

| Variable | Values | Description |
|----------|--------|-------------|
| N-gram order | 2 (primary), 3 (if needed) | Context window size |
| Smoothing method | Stupid Backoff, Jelinek-Mercer, Modified Kneser-Ney, Katz Backoff | How unseen n-grams are handled |
| Interpolation weight | lambda in {0.1, 0.3, 0.5, 0.7, 0.9} | Bigram vs unigram mixing weight (Jelinek-Mercer) |
| Backoff weight | alpha in {0.2, 0.4, 0.6} | Backoff penalty (Stupid Backoff) |
| Corpus combination | Individual corpora, merged | Whether to merge counts across corpora |
| Context source | No context, within-input, last committed word | Where bigram context comes from |

## Evaluation Metrics

| Metric | Description | Baseline (from 006) |
|--------|-------------|---------------------|
| MRR (no context) | Mean Reciprocal Rank on ambiguous inputs without context | 0.960 |
| MRR (with context) | MRR on ambiguous inputs with preceding context | N/A (new) |
| Top-1 accuracy (no context) | % of correct top candidate without context | 92.0% |
| Top-1 accuracy (with context) | % of correct top candidate with context | N/A (new) |
| Context improvement | Delta MRR between no-context and with-context | N/A (new) |
| Unseen bigram rate | % of test bigrams not found in training data | N/A (new) |

## Datasets

### Existing

- **Ranking benchmark (Set B from 006):** 25 ambiguous inputs, no context — used as no-context baseline
- **Raw corpora:** wisesight, wongnai, prachathai, thwiki (in `data/corpora/raw/`)
- **Trie dataset:** ~5K words with frequencies (from pipeline CP07)

### To Be Created

- **Ranking benchmark with context:** New benchmark at `benchmarks/ranking/` following the spec in `docs/benchmarks.md`. Context-dependent test cases where the correct candidate changes based on preceding word(s). Maintainer provides native-speaker ground truth for expected rankings.
- **Bigram frequency table:** Extracted from tokenized corpora. Format: `(word_i, word_j, count)` TSV.
- **Trigram frequency table (if needed):** Same format with 3-word tuples.

## Procedure

### Phase 1: Ranking Benchmark Creation

**Collaborative: agent drafts, maintainer validates.**

1. Agent analyzes existing trie vocabulary for ambiguous romanization collisions (multiple Thai words sharing a romanization key)
2. Agent generates candidate context-dependent test cases based on corpus co-occurrence patterns
3. Maintainer reviews, corrects, and adds cases based on native speaker intuition
4. Produce benchmark CSV at `benchmarks/ranking/v0.1.0.csv` with columns: `latin_input, context, expected_top, valid_alternatives, notes`
5. Target: 50-100 test cases covering common ambiguities with and without context

### Phase 2: N-gram Extraction Pipeline

**Collaborative: agent writes scripts, maintainer runs in devcontainer.**

1. Write tokenization script that processes each corpus using PyThaiNLP/TLTK word segmentation
2. Write n-gram counting script (parameterized by n) that:
   - Counts all n-grams from tokenized output
   - Filters to vocabulary present in the trie dataset
   - Merges counts across corpora (simple summation)
   - Outputs TSV: `word_1 \t word_2 \t ... \t word_n \t count`
3. Maintainer runs scripts in devcontainer, shares output files
4. Agent analyzes n-gram statistics: total unique bigrams, coverage of trie vocabulary, most frequent bigrams, distribution shape

### Phase 3: Smoothing Evaluation

**Primarily agent work, with maintainer review.**

1. Implement 4 smoothing methods:
   - **Stupid Backoff** (baseline): `Score(w2|w1) = count(w1,w2)/count(w1)` if seen, else `alpha * P_unigram(w2)`. Not true probabilities — just scores. Alpha typically 0.4. (Brants et al. 2007)
   - **Jelinek-Mercer interpolation** (practical workhorse): `P(w2|w1) = lambda * P_bigram(w2|w1) + (1-lambda) * P_unigram(w2)`. Always blends both orders. Lambda tuned on held-out data. Used by libpinyin in production.
   - **Modified Kneser-Ney** (theoretical best): Three discount values (D1, D2, D3+) based on count, with continuation probability for lower-order distribution. Gold standard in KenLM/SRILM. (Chen & Goodman 1999)
   - **Katz Backoff** (alternative philosophy): Good-Turing discounted counts for seen bigrams; normalized backoff to unigram for unseen. Tests backoff-vs-interpolation question.
2. Evaluate each method on the ranking benchmark:
   - Run bigram-aware scoring on all bigram-type test cases (110 rows)
   - Measure MRR, Top-1 accuracy, and context improvement
   - Sweep parameters: lambda for Jelinek-Mercer, alpha for Stupid Backoff
   - Compare across smoothing methods
3. Analyze failure cases: which test cases does bigram scoring fix vs break vs leave unchanged?

**Rationale for method selection:**
- Add-alpha dropped: consistently worst performer in literature; Stupid Backoff is equally simple but better.
- Basic Kneser-Ney dropped: Modified KN is strictly superior with minimal extra complexity.
- Absolute discounting, Witten-Bell: dominated by MKN, no unique design-space coverage.
- The four selected methods span: simple baseline → practical middle → theoretical best → alternative philosophy (backoff vs interpolation).

### Phase 4: Viterbi Integration Prototype

**Agent implements, maintainer validates on real inputs.**

1. Extend the Research 005 Viterbi prototype with bigram transition costs:
   - State becomes `(position, previous_word_id)` instead of `(position)`
   - Edge cost: `cost(w_j | w_i) = -log(P_smoothed(w_j | w_i))`
   - Backoff: if bigram unseen, fall back to unigram cost with interpolation
2. Support context seeding: accept last committed word as initial state
3. Validate on ranking benchmark and compare against unigram baseline
4. Performance check: confirm still sub-millisecond on realistic lattice sizes

### Phase 5: Trigram Assessment (Conditional)

**Only if bigram results suggest insufficiency.**

1. Re-run extraction pipeline with n=3
2. Evaluate trigram Viterbi on cases where bigram failed or was marginal
3. Quantify marginal improvement vs storage/complexity cost
4. Recommend whether trigram is worth implementing for THAIME

### Phase 6: Summary and Recommendation

1. Write `research/007-bigram-scoring/summary.md` with concrete findings
2. Deliverables to merge to main:
   - Summary document
   - Ranking benchmark (`benchmarks/ranking/v0.1.0.csv`)
   - N-gram extraction pipeline scripts (if production-quality, to `pipelines/`)
   - Any shared utilities added to `src/utils/`
3. Open PR from `summary/007-bigram-scoring` -> `main`

## Success Criteria

| Criterion | Threshold |
|-----------|-----------|
| Context-dependent MRR improvement | MRR (with context) > 0.960 (the unigram baseline on ambiguous inputs) |
| No regression on no-context cases | MRR (no context) >= 0.960 |
| Unseen bigram handling | Smoothed model gracefully handles >90% unseen bigrams without degradation |
| Practical recommendation | Clear, implementable formula for the Rust engine |

The primary success criterion is demonstrating that bigram scoring improves ranking on context-dependent cases without regressing context-free cases. Even a modest improvement (e.g., MRR 0.960 -> 0.980) validates the approach, since it proves the architecture works and can be improved with more training data.

## Collaboration Model

This research is explicitly collaborative between agent and maintainer:

- **Agent** handles: literature review, script writing, data analysis, prototype implementation, summary writing
- **Maintainer** handles: running scripts in devcontainer, providing native-speaker validation for benchmarks, reviewing bigram quality, testing with real Thai input patterns
- **Shared:** benchmark creation (agent proposes, maintainer validates), research direction decisions

## Dependencies

```
# Already available in devcontainer
pythainlp
tltk
pandas
numpy
matplotlib

# May need
collections (stdlib)
csv (stdlib)
math (stdlib)
```

No new external dependencies expected. All code runs in the existing devcontainer environment.

## Branch Strategy

All work lives on `research/007-bigram-scoring`. When complete:
- Summary and benchmarks merge to main via `summary/007-bigram-scoring`
- Pipeline scripts merge if production-quality, otherwise stay on research branch
- Experimental artifacts (intermediate data, notebooks) stay on research branch
