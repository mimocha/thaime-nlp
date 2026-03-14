# Research Index — thaime-nlp

## Completed Research

| # | Topic | Date | Key Finding | Summary |
|---|-------|------|-------------|---------|
| 1 | Romanization Source Audit | 2026-03-04 | TLTK is the best base source (98.75% accuracy); no source produces informal romanization | [research/001-romanization-source-audit/summary.md](001-romanization-source-audit/summary.md) |
| 2 | Informal Romanization Variants | 2026-03-04 | Rule-based variant generator achieves 91.2% coverage with 5.0 avg variants/word | [research/002-informal-romanization-variants/summary.md](002-informal-romanization-variants/summary.md) |
| 3 | Component Romanization | 2026-03-07 | Romanization of onset/vowel/coda components works and scales better than word-level romanization, reproducing 89% of v0.1.0 benchmark | [research/003-component-romanization/summary.md](003-component-romanization/summary.md) |
| 4 | Trie Data Structure Selection | 2026-03-08 | Double-array trie (DARTS) is the best all-around choice; recommend `yada` Rust crate for production. MARISA-trie is 5× smaller but 2–3× slower for common prefix search. | [research/trie-selection/summary.md](004-trie-selection/summary.md) |
| 5 | Candidate Selection Algorithm | 2026-03-09 | Viterbi DP with k-best tracking on a word lattice, scoring via -log(freq) + segmentation penalty. All surveyed IMEs (Mozc, librime, libkkc, Anthy) use this pattern. Sub-millisecond performance confirmed. | [research/005-candidate-selection/summary.md](005-candidate-selection/summary.md) |
| 6 | Word Frequency Scoring | 2026-03-11 | Current baseline `-log(freq)` is near-optimal (MRR=0.989/0.960). No alternative formula improves over it. λ has no effect on single-word ranking. Next improvement requires bigram scoring. | [research/006-frequency-scoring/summary.md](006-frequency-scoring/summary.md) |
| 7 | N-gram Transition Probability | 2026-03-14 | Stupid Backoff recommended (statistically indistinguishable from MKN/Katz); bigram_weight=2.0 captures 64% of max gain; trigram safe with backoff. Benchmark reliability limits fine-grained comparisons. | [research/007-bigram-scoring/summary.md](007-bigram-scoring/summary.md) |

## In Progress

*None*

## Future Research

Topics identified during completed research that warrant dedicated investigation:

| Topic | Origin | Priority | Description |
|-------|--------|----------|-------------|
| Benchmark Reliability | R007 | High | Current 200-row ranking benchmark cannot discriminate between smoothing methods (~55 effective rows). Needs expansion to 500+ rows with balanced coverage, compound-aware test design, and bootstrap confidence intervals. Blocks further scoring method comparisons. |
| Repeater ๆ Handling | R007 | Medium | Maiyamok (ๆ) is currently filtered during tokenization, suppressing n-gram signal for repeater contexts. Needs: (1) normalization of ๆ runs to a single token during n-gram counting, (2) engine-side design for repeater candidate selection (wildcard matching against preceding Latin input). |
| PMI-Based Scoring | R007 | Medium | Pointwise Mutual Information addresses dominant-word frequency imbalance (69% of ranking misses). Normalizes out marginal frequency so ultra-common words like ไม่, การ, จะ don't always dominate. Requires raw counts (available from n-gram pipeline). |
| Special Tokenization Tokens | R007 | Low | Replace dropped non-Thai tokens with typed markers (`<NUMBER>`, `<LATIN>`) instead of plain boundaries. Enables patterns like [วันที่, `<NUMBER>`, ธันวาคม] to carry more context than boundary-only. Requires engine support for special tokens in Viterbi. |
| SentencePiece Tokenization | R007 | Low | Data-driven subword tokenization may resolve compound tokenization issues and improve n-gram coverage. Could serve as (a) independent benchmark generation method for cross-validation, or (b) alternative tokenizer for production n-gram counts. Significant research effort — training, evaluation, mapping to trie vocab. |
| Frequency Dampening | R007 | Low | Sublinear scaling (e.g., log-frequency) to reduce dominance of ultra-high-frequency words in n-gram scoring. Related to PMI-based scoring but simpler to implement. |
