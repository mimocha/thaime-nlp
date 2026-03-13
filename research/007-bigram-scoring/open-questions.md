# Research 007: Open Questions for Follow-up Research

**Date:** 2026-03-13
**Context:** Phase 3 (Smoothing Evaluation) and Phase 4 (Bigram Viterbi) findings

## 1. Benchmark Reliability — Proposed Follow-up Research Topic

### Problem

Multiple lines of evidence from Phases 3 and 4 indicate the current bigram ranking benchmark (v0.1.1, 110 bigram-type rows) has systematic issues that limit its usefulness for evaluating scoring methods.

**Phase 3 finding — insufficient discriminating power:**
- **30/110 rows (27%) have unseen expected bigrams** — all methods fall back to unigram with identical rankings (3.3% Top-1 across all methods).
- **55/110 rows (50%) produce the same top-1 winner as pure unigram** — context had no effect on the ranking for these rows.
- **Effective discriminating sample is ~55 rows** — method differences amount to 2-7 rows, well within noise.

**Phase 4 finding — compound tokenization contaminates training data:**

Analysis of the full 162K tokenizer wordlist revealed that 22/110 bigram-type benchmark rows have their context+expected pair as a single compound word in the tokenizer vocabulary. When the tokenizer processes corpus text, it produces these compounds as single tokens, suppressing the component bigram signal:

| Condition | Miss rate (bw=3.0) | N |
|---|---|---|
| Compound in wordlist | **95.5%** | 21/22 |
| Compound NOT in wordlist | 53.4% | 47/88 |

13 of the 21 compound misses have **zero bigram count** — the bigram was completely eaten by compound tokenization (e.g., เติบโต, ป้องกัน, ลูกไก่, ตีโต้, ลั่นไก). The remaining 8 have counts of 1-32 — vastly suppressed. This means ~20% of bigram-type benchmark rows are testing pairs where the training data is systematically biased against the correct answer.

**Combined effect:** Between unseen bigrams (27%), compound-eaten bigrams (~20%), and dominant-word imbalance (covered in §2), the benchmark has multiple confounding factors that make it unreliable for comparing scoring methods.

### Result

All backoff-family methods (Stupid Backoff, Katz, MKN) hit the same Top-1 ceiling of 42.7% (47/110). MRR differences between them are <0.02 — statistically meaningless at this sample size. The choice between smoothing methods cannot be made on current evidence.

### Recommended Follow-up

This warrants a dedicated research topic to investigate benchmark reliability and propose improvements:

1. **Audit existing rows** — classify all 110 bigram rows by failure mode (compound tokenization, unseen bigram, dominant-word, genuine model failure) to understand the true effective sample
2. **Expand the benchmark** — target 500+ bigram-type rows, with systematic coverage of:
   - Different bigram count ranges (count=1, 2-5, 5-20, 20-100, 100+)
   - Balanced representation across ambiguity levels (2-candidate, 5-candidate, 10+ candidate groups)
   - More latin_input groups (currently only 13)
3. **Compound-aware test design** — exclude or separately tag rows where compound tokenization suppresses the bigram signal, so they don't contaminate method comparisons
4. **Use corpus-driven test case generation** — instead of hand-curation, sample (context, candidate) pairs directly from corpus data to avoid selection bias
5. **Include negative cases** — rows where unigram ranking is already correct, to measure whether bigram scoring introduces regressions
6. **Statistical significance testing** — bootstrap confidence intervals on MRR/Top-1 to determine if method differences are real


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


## 3. Compound Tokenization Suppresses Bigram Signal

### Problem

Phase 4 analysis revealed that the tokenizer (newmm) treats many context+expected pairs as single compound tokens during corpus processing. The full tokenizer wordlist (162K entries, much larger than the 15K trie dictionary) contains compound forms like เติบโต, ป้องกัน, ลูกไก่, ตีโต้ — when the tokenizer encounters these in running text, it produces one token instead of two, so the component bigram is never counted.

This affects 22/110 bigram-type benchmark rows (20%), with a 95.5% miss rate at bw=3.0. Of these, 13 have zero bigram count and 8 have counts of 1-32.

### Why this is fundamental

This is not a bug — it's an inherent tension between tokenizer granularity and n-gram model assumptions. The tokenizer is designed to produce the longest matching word, which is correct for many NLP tasks but directly conflicts with bigram counting. Both the "compound" and "decomposed" tokenizations are linguistically valid.

### Recommended Follow-up

1. **Dual tokenization** — Run corpus tokenization at two granularities (word-level and subword-level) and merge the bigram counts, giving credit to both compound and decomposed forms.
2. **Dictionary-based bigram injection** — For known compound words in the trie, synthetically inject bigram counts for their decomposed forms based on the compound's unigram frequency.
3. **SentencePiece tokenization** — Data-driven subword tokenization (BPE/Unigram model) avoids the longest-match bias of dictionary-based tokenizers and may naturally produce more decomposed bigrams.


## 4. Unseen Bigram Handling

### Problem

30/110 benchmark rows (27%) have expected bigrams not found in any training corpus. For these cases, all methods collapse to unigram ranking with 3.3% Top-1 accuracy. This represents a hard ceiling that no smoothing method can break. Note: some of these unseen bigrams are likely caused by the compound tokenization issue described in §3.

### Recommended Follow-up

1. **SentencePiece / BPE tokenization** — Current newmm tokenizer produces under-segmented compounds and misses some valid word boundaries. Data-driven subword tokenization may improve coverage.
2. **Additional corpora** — The current 4 corpora (107M tokens) cover 72.7% of benchmark bigrams. Adding domain-specific corpora (e.g., conversational Thai, social media) could improve coverage for informal/colloquial pairs.
3. **Synthetic bigram generation** — Use word embeddings or dictionary-based heuristics to estimate scores for unseen bigrams (e.g., words in the same semantic cluster may have similar transition probabilities).


## 5. MKN Discount Parameter Anomaly

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
