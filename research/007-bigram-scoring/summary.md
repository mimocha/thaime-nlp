# N-gram Transition Probability for Candidate Ranking

**Date:** 2026-03-14
**Author:** THAIME Research (agent + maintainer)
**Branch:** research/007-bigram-scoring
**Status:** Complete

## Research Question

How should n-gram transition probabilities be extracted, smoothed, and integrated into THAIME's Viterbi scoring to improve context-dependent candidate ranking over the unigram baseline?

## Approach

Built a complete n-gram extraction and evaluation pipeline across 5 phases:

1. **Ranking benchmark** — Created a 200-row benchmark (`benchmarks/ranking/bigram/v0.1.1.csv`) with 3 row types: baseline (17, no context), bigram (110, context-dependent), and compound (73, compound word disambiguation). Maintainer provided native-speaker ground truth.

2. **N-gram extraction** — Tokenized 4 Thai corpora (wisesight, wongnai, prachathai, thwiki; ~107M tokens total) using PyThaiNLP `newmm`, extracted bigram and trigram counts filtered to the trie vocabulary (15K words). Produced both raw-sum and normalized-equal-weight merges.

3. **Smoothing evaluation** — Evaluated 4 smoothing methods (Stupid Backoff, Jelinek-Mercer, Modified Kneser-Ney, Katz Backoff) on the benchmark's 110 bigram-type rows. Methods are compared by scoring (context_word, candidate_word) pairs and ranking candidates for each latin_input.

4. **Bigram-aware Viterbi prototype** — Integrated Stupid Backoff into a Viterbi candidate selection algorithm using the real trie dataset (15K words, 187K romanization keys). Swept bigram_weight parameter and analyzed failure modes.

5. **Trigram assessment** — Extracted trigram counts (min-count=2) and evaluated coverage against the benchmark to determine whether trigrams are worth implementing alongside bigrams.

## Key Findings

### Smoothing method selection

- **All smoothing methods are statistically indistinguishable on the current benchmark.** Stupid Backoff, Jelinek-Mercer, Modified Kneser-Ney, and Katz Backoff all hit the same Top-1 ceiling of 42.7% (47/110) on bigram-type rows. MRR differences are <0.02.
- The benchmark cannot discriminate between methods: 30/110 rows (27%) have unseen bigrams (all methods fall back identically), 55/110 (50%) produce the same top-1 as pure unigram.
- **Stupid Backoff is recommended for production.** Trivial to implement in Rust (one hash lookup + branch), no parameter estimation needed, performs within noise of theoretically superior methods.

### Bigram Viterbi integration

- **Bigram scoring improves context-dependent ranking significantly.** On bigram-type rows, MRR improves from 0.326 (unigram) to 0.560 at bigram_weight=3.0 (+72%). Top-1 accuracy improves from 10.0% to 38.2%.
- **Baseline rows are unaffected.** 100% MRR across all bigram weight values, confirming the `<BOS>` fallback works correctly.
- **Compound rows are neutral.** MRR stays at ~0.40 regardless of bigram weight — compound disambiguation depends on segmentation, not bigram context.
- **Diminishing returns past bigram_weight=2.0.** The 0→1 jump (+0.17 MRR) dwarfs 2→3 (+0.025 MRR). Recommended default: bigram_weight=2.0.

| bigram_weight | Overall MRR | Overall Top-1 | Baseline MRR | Bigram MRR | Compound MRR |
|---|---|---|---|---|---|
| 0.0 (unigram) | 0.413 | 21.5% | **1.000** | 0.326 | 0.406 |
| 1.0 | 0.502 | 29.0% | **1.000** | 0.497 | 0.394 |
| 2.0 | 0.526 | 33.0% | **1.000** | 0.536 | 0.402 |
| 3.0 | 0.540 | 35.5% | **1.000** | 0.560 | 0.402 |

### Failure mode analysis

Two distinct failure modes account for all 68 bigram-row misses at bw=3.0:

1. **Compound tokenization suppresses bigram signal (31% of misses).** When context+expected exists as a compound word in the tokenizer's 162K vocabulary (e.g., เติบโต, ป้องกัน, ลูกไก่), the tokenizer produces it as a single token during corpus processing, preventing the component bigram from being counted. 22/110 bigram-type rows are affected; these have a 95.5% miss rate vs 53.4% for non-compound rows.

2. **Dominant-word frequency imbalance (69% of misses).** Ultra-frequent words (ไม่, การ, จะ, แต่) have such high unigram+bigram counts that they dominate their romanization groups regardless of context. Smoothing cannot fix this because these words are common continuations of *every* context word.

### Trigram assessment

- Trigram data is available: 9.9M unique trigrams (raw merged, min-count≥2) from the same 4 corpora.
- **Trigram coverage is a strict subset of bigram coverage.** Every benchmark row with trigram evidence also has bigram evidence; 68/80 (85%) of rows with bigram counts also have trigram evidence.
- The current benchmark cannot measure trigram improvement (inputs are single-word, context is one word deep).
- **Trigrams are recommended for production** based on established literature (1.6x perplexity reduction) and safe fallback: the Stupid Backoff chain trigram→bigram→unigram guarantees no degradation.

### Benchmark reliability

Multiple findings indicate the benchmark has systematic limitations:

- 27% of bigram-type rows have unseen expected bigrams — untestable
- ~20% are contaminated by compound tokenization — systematically biased against the correct answer
- Effective discriminating sample is ~55 rows — too small for method comparison
- Dominant-word imbalance makes ~69% of misses structurally unsolvable without a different scoring approach

**Benchmark reliability warrants a dedicated follow-up research topic** before revisiting method comparisons or parameter tuning.

## Recommendation

### For the THAIME production engine

1. **Scoring method:** Stupid Backoff with trigram→bigram→unigram fallback chain.
   ```
   score(w3 | w1, w2):
     if count(w1, w2, w3) > 0: return count(w1,w2,w3) / count(w1,w2)
     elif count(w2, w3) > 0:   return alpha * count(w2,w3) / count(w2)
     else:                     return alpha^2 * P_unigram(w3)
   ```

2. **Parameters:**
   - `alpha = 0.4` (Stupid Backoff penalty; standard value, insensitive on current benchmark)
   - `bigram_weight = 2.0` (balances bigram gain with compound neutrality)
   - `segmentation_penalty = 0.5` (from Research 005; confirmed insensitive here)

3. **Viterbi state expansion:** State becomes `(position, prev_thai_text)` for bigram, or `(position, prev2, prev1)` for trigram. k-best pruning per state keeps complexity manageable.

4. **Data artifacts for engine consumption:**
   - Bigram counts: `ngrams_2_merged_raw.tsv` (8.1M entries, ~180 MB)
   - Trigram counts: `ngrams_3_merged_raw.tsv` (9.9M entries, ~447 MB)
   - Both can be compressed significantly for deployment (hash map or sorted array with binary search)

### For follow-up research

| Topic | Priority | Rationale |
|---|---|---|
| Benchmark reliability investigation | High | Current benchmark cannot discriminate methods or measure improvements reliably; blocks further scoring research |
| PMI-based scoring | Medium | Addresses dominant-word imbalance (69% of misses); frequency dampening is an alternative |
| N-gram pipeline productionization | Medium | Move tokenize/count scripts to `pipelines/ngram/`; fix number-bridged false bigrams |
| SentencePiece tokenization | Low | Data-driven tokenization may improve n-gram coverage; addresses compound tokenization issue |

## Limitations

- **Benchmark is unreliable for fine-grained comparisons.** The 200-row benchmark has known contamination (compound tokenization), small effective sample (~55 discriminating rows), and dominant-word confounds. Results should be interpreted directionally (bigrams help) rather than precisely (MRR=0.536 at bw=2.0).
- **Trigram improvement is not measured.** The assessment confirms data availability and safe fallback, but actual improvement requires a benchmark with two-word context or multi-word inputs.
- **Compound tokenization issue is not resolved.** The tokenizer's 162K vocabulary contains compound forms that suppress bigram counts during training. This is a fundamental tension between tokenizer granularity and n-gram model assumptions.
- **Only newmm tokenizer evaluated.** Alternative tokenizers (TLTK, SentencePiece) may produce different and potentially better n-gram distributions.
- **No multi-word input testing.** The Viterbi prototype supports multi-word lattice paths but the benchmark only tests single-word disambiguation.

## References

- Experiment branch: `research/007-bigram-scoring`
- Research 005 (Candidate Selection): Viterbi algorithm design and lattice construction
- Research 006 (Frequency Scoring): Unigram baseline (MRR=0.960 on ambiguous inputs)
- Brants et al. 2007 — "Large Language Models in Machine Translation" (Stupid Backoff)
- Chen & Goodman 1999 — "An Empirical Study of Smoothing Techniques" (Modified Kneser-Ney)
- Jurafsky & Martin, SLP3 Ch. 3 — N-gram perplexity benchmarks (bigram 5.7x, trigram 1.6x improvement)
- Benchmark: `benchmarks/ranking/bigram/v0.1.1.csv`
- N-gram extraction scripts: `experiments/007-bigram-scoring/scripts/`
- Tokenization issues analysis: `research/007-bigram-scoring/tokenization-issues.md`
- Open questions for follow-up: `research/007-bigram-scoring/open-questions.md`
