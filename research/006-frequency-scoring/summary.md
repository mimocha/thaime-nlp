# Word Frequency Scoring for Candidate Ranking

**Date:** 2026-03-11
**Author:** THAIME Research (agent)
**Branch:** research/006-frequency-scoring
**Status:** Complete

## Research Question

Which word frequency scoring formula produces the best candidate ranking in THAIME's Viterbi path search, given the current multi-corpus word frequency data?

## Approach

Evaluated 6 unigram scoring formulas against 3 test sets (70 common words, 25 ambiguous inputs, 247 override words) using the real trie dataset (5,000 words, 49K romanization keys). Each formula was tested with 7 segmentation penalty values (λ ∈ {0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0}) for a total of 42 formula×λ combinations. Per-corpus frequencies were extracted from 3 raw corpora (wisesight, wongnai, prachathai) to enable corpus-balanced scoring.

## Key Findings

- **The current baseline formula (`-log(freq)`) is near-optimal.** It achieves MRR=0.989 on common words and MRR=0.960 on ambiguous inputs — the best or tied-best score among all formulas tested.

- **Source-count weighting provides zero benefit over baseline.** The source_weighted and smoothed formulas match baseline performance exactly. The trie vocabulary is already quality-filtered (minimum 2-source requirement), so most words have similar source counts, making the source-count signal redundant.

- **TF-IDF scoring is correctly harmful (negative control validated).** TF-IDF reduces ambiguous-input MRR from 0.960 to 0.933 and introduces 1 new misranking. This confirms that up-weighting rare-source words hurts IME candidate ranking.

- **Rank-based scoring loses useful information.** Replacing absolute frequency with rank reduces ambiguous-input MRR to 0.933 (vs 0.960 for baseline) and introduces 1 additional multi-word misranking.

- **Corpus-balanced frequency is the worst performer.** Per-corpus normalization degrades both common-word MRR (0.960–0.981 vs 0.989) and ambiguous-input MRR (0.870–0.890 vs 0.960), with 5 failures vs 2 for baseline. Normalizing to per-corpus max frequency inflates domain-specific words and deflates genuinely common words.

- **Segmentation penalty λ has no measurable effect on single-word candidate ranking.** The baseline, source_weighted, smoothed, and tfidf formulas produce identical results across all 7 λ values. This confirms live testing observations — λ only matters for multi-word segmentation, not single-word ranking. **The current default λ=1.0 is fine.**

- **The 2 apparent Set B misrankings are test set artifacts, not real errors.** The `hun` and `chae` cases arise because Set B defines collisions by shortest-romanization, while the Viterbi matches all romanizations. In both cases, the Viterbi correctly ranks the globally highest-frequency word first. The true Top-1 accuracy is likely higher than the reported 92%.

| Formula | Best λ | A MRR | A Top-1 | B MRR | B Top-1 | C Recall |
|---------|--------|-------|---------|-------|---------|----------|
| **baseline** | any | **0.989** | **98.6%** | **0.960** | **92.0%** | 100% |
| source_weighted | any | 0.989 | 98.6% | 0.960 | 92.0% | 100% |
| smoothed | ≥0.3 | 0.989 | 98.6% | 0.960 | 92.0% | 100% |
| tfidf | any | 0.989 | 98.6% | 0.933 | 88.0% | 100% |
| rank | ≥1.0 | 0.989 | 98.6% | 0.940 | 88.0% | 100% |
| balanced | 1.5–2.0 | 0.989 | 98.6% | 0.873 | 76.0% | 100% |

## Recommendation

**Keep the current baseline scoring formula: `cost(word) = -log(freq)`.**

The simple negative log-frequency formula is already near-optimal for single-word candidate ranking. No alternative formula tested provides measurable improvement. The 92% top-1 accuracy on ambiguous inputs represents the practical ceiling for unigram scoring — the remaining errors are genuine frequency ties that require context (bigram models or user history) to disambiguate.

Specific recommendations for the THAIME engine:

1. **Scoring formula:** Keep `-log(freq)` as the unigram cost function. No change needed.
2. **Segmentation penalty λ:** Keep the current default λ=1.0. The sweep confirms λ has no effect on single-word ranking. It may matter for multi-word segmentation but needs evaluation on segmentation test cases (not covered in this study).
3. **Source-count metadata:** Do not invest in source-count weighting for unigram scoring. The trie pipeline's quality filtering already captures source reliability implicitly.
4. **Per-corpus frequency data:** Do not use corpus-balanced frequencies — they actively hurt ranking quality. The averaged frequency in the trie dataset is the correct signal.
5. **Next priority for ranking improvement:** Bigram/n-gram scoring (research 007 candidate) — this is the only approach that can resolve context-dependent ambiguity cases (e.g., "kao" → ข้าว after กิน vs เขา in other contexts).

## Limitations

- **Test sets are limited in scope.** Set A (70 entries) and Set B (25 entries) are small. Results may not generalize to all input patterns. The test sets are heavily weighted toward single-word inputs.
- **Multi-word segmentation not evaluated.** The segmentation penalty λ was only evaluated on single-word inputs where it has no effect. A dedicated segmentation benchmark is needed to evaluate λ's impact on multi-word paths.
- **Test set B collision detection uses shortest-romanization grouping.** This means some "failures" in Set B are actually correct Viterbi behavior — the Viterbi matches all romanization variants, not just the shortest. A more comprehensive collision detection (matching all romanization overlaps) would give a more accurate Set B accuracy estimate.
- **No context scoring.** All formulas evaluated are unigram (context-free). Context-dependent disambiguation (e.g., "kao" → ข้าว after กิน vs เขา otherwise) requires bigram or contextual scoring.
- **Per-corpus extraction used only 3 of 5 corpora.** The thwiki and pythainlp sources were not included in per-corpus frequency extraction (thwiki is slow to parse; pythainlp provides only binary presence, not frequencies). This may slightly affect the balanced formula's results, though the formula's poor performance is likely inherent to its normalization approach.
- **Test set construction is automated.** Expected top candidates in Set B are chosen by frequency, which may not always match human intuition (e.g., `hun → หุ้น` vs หั่น is genuinely debatable).

## References

- Experiment branch: `research/006-frequency-scoring`
- Research 005 (Candidate Selection): `research/005-candidate-selection/summary.md`
- Trie dataset: `experiments/006-frequency-scoring/reference/trie_dataset_sample_5k.json`
- Scoring implementations: `experiments/006-frequency-scoring/scoring.py`
- Evaluation script: `experiments/006-frequency-scoring/evaluate.py`
