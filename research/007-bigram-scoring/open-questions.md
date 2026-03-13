# Research 007: Open Questions for Follow-up Research

**Date:** 2026-03-13
**Context:** Phase 3 (Smoothing Evaluation) findings

## 1. Benchmark Insufficiency for Smoothing Method Discrimination

### Problem

The current bigram ranking benchmark (v0.1.1, 110 bigram-type rows) cannot reliably discriminate between smoothing methods. Diagnostic analysis revealed:

- **30/110 rows (27%) have unseen expected bigrams** — all methods fall back to unigram with identical rankings (3.3% Top-1 across all methods).
- **55/110 rows (50%) produce the same top-1 winner as pure unigram** — context had no effect on the ranking for these rows.
- **Effective discriminating sample is ~55 rows** — and even within these, method differences amount to 2-7 rows, well within noise for a hand-curated benchmark.

### Result

All backoff-family methods (Stupid Backoff, Katz, MKN) hit the same Top-1 ceiling of 42.7% (47/110). MRR differences between them are <0.02 — statistically meaningless at this sample size. The choice between smoothing methods cannot be made on current evidence.

### Recommended Follow-up

A dedicated research topic should:

1. **Expand the benchmark** — target 500+ bigram-type rows, with systematic coverage of:
   - Different bigram count ranges (count=1, 2-5, 5-20, 20-100, 100+)
   - Balanced representation across ambiguity levels (2-candidate, 5-candidate, 10+ candidate groups)
   - More latin_input groups (currently only 13)
2. **Use corpus-driven test case generation** — instead of hand-curation, sample (context, candidate) pairs directly from corpus data to avoid selection bias
3. **Include negative cases** — rows where unigram ranking is already correct, to measure whether bigram scoring introduces regressions
4. **Statistical significance testing** — bootstrap confidence intervals on MRR/Top-1 to determine if method differences are real


## 2. Dominant-Word Frequency Imbalance

### Problem

High-frequency words (ไม่, การ, จะ, แต่, ชาว) dominate their romanization groups so heavily that their bigram co-occurrence with almost any context word exceeds the correct-but-rarer candidate. This is not a smoothing problem — it's a data distribution problem.

| Group | Dominant | Freq | Rows needing to beat it | Succeed |
|-------|----------|------|------------------------|---------|
| kan | การ | 8.75e-03 | 6/6 | 0/6 (0%) |
| mai | ไม่ | 1.31e-02 | 8/8 | 1/8 (12%) |
| tae | แต่ | 5.54e-03 | 6/11 | 1/6 (17%) |
| tai | ไทย | 2.11e-03 | 8/8 | 2/8 (25%) |

For "kan", bigram scoring **never** beats the unigram-dominant การ — across all 6 test cases, all 4 smoothing methods fail.

### Why smoothing doesn't help

Smoothing redistributes probability mass from seen to unseen events. But the dominant words are seen with *every* context (they have high bigram counts universally), so smoothing has nothing to redistribute toward the correct but rarer candidate.

### Recommended Follow-up

Investigate alternative scoring approaches:

1. **PMI-based scoring** — Pointwise Mutual Information measures association strength relative to expectation: `PMI(w1,w2) = log(P(w1,w2) / P(w1)P(w2))`. This normalizes out marginal frequency, so a rare-but-specific bigram (กิน, ข้าว) scores higher than a common-but-generic one (กิน, ไม่).
2. **Frequency dampening** — Apply sublinear scaling (e.g., log-frequency) to reduce the dominance of ultra-high-frequency words before computing conditional probabilities.
3. **Context-dependent interpolation** — Weight the bigram component higher when the context word is informative (low entropy over continuations) and lower when it's uninformative.


## 3. Unseen Bigram Handling

### Problem

30/110 benchmark rows (27%) have expected bigrams not found in any training corpus. For these cases, all methods collapse to unigram ranking with 3.3% Top-1 accuracy. This represents a hard ceiling that no smoothing method can break.

### Recommended Follow-up

1. **SentencePiece / BPE tokenization** — Current newmm tokenizer produces under-segmented compounds and misses some valid word boundaries. Data-driven subword tokenization may improve coverage.
2. **Additional corpora** — The current 4 corpora (107M tokens) cover 72.7% of benchmark bigrams. Adding domain-specific corpora (e.g., conversational Thai, social media) could improve coverage for informal/colloquial pairs.
3. **Synthetic bigram generation** — Use word embeddings or dictionary-based heuristics to estimate scores for unseen bigrams (e.g., words in the same semantic cluster may have similar transition probabilities).


## 4. MKN Discount Parameter Anomaly

### Observation

With `--min-count 1` data, Modified Kneser-Ney computed discounts D1=0.622, D2=1.087, D3+=1.490. While mathematically valid (they still produce non-negative discounted counts), D2>1 and D3>1 are unusually high — typical values in the literature are all <1.

This may indicate that the count distribution is skewed by the corpus merge strategy (summing raw counts across 4 corpora) or by the vocabulary filter creating artificial count patterns.

### Impact

MKN's aggressive discounting may be weakening the signal from correctly-seen bigrams, redistributing too much mass to continuation probability. This could explain why MKN underperforms Stupid Backoff on seen bigrams (56.2% vs 57.5% Top-1).

### Recommended Follow-up

If a future study revisits smoothing methods with an improved benchmark:
- Compute MKN discounts per-corpus before merging
- Compare raw-sum merge vs normalized merge for count-of-count statistics
- Validate discount values against published baselines for comparable corpus sizes
