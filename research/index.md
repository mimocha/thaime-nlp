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
| 7 | N-gram Transition Probability | 2026-03-14 | Bigram scoring improves context-dependent MRR by +72% over unigram. Stupid Backoff recommended as MVP implementation, with trigram→bigram→unigram fallback. Benchmark reliability is a known limitation. | [research/007-bigram-scoring/summary.md](007-bigram-scoring/summary.md) |

## In Progress

| Topic | Branch | Stage | Started |
|-------|--------|-------|---------|

