# Research 007: Bigram Scoring — Progress Notes

**Last updated:** 2026-03-13
**Branch:** `research/007-bigram-scoring`

## Current Status: Phase 2 complete, Phase 3 next

### Phase 1: Ranking Benchmark — Complete

- 200 test cases in `benchmarks/ranking/bigram/v0.1.0.csv` (original)
- v0.1.1 adds `type` column tagging rows as `baseline` (17), `bigram` (110), `compound` (73)
  - File: `benchmarks/ranking/bigram/v0.1.1.csv`
  - Compound tagging based on whether `context + expected_top` exists as a single word in trie vocab (15K words)
- Some bigram-tagged rows may still be compound-like (e.g. สีขาว, ดีไหม, มีแต่, วิบากกรรม) — maintainer to review

### Phase 2: N-gram Extraction Pipeline — Complete

**Scripts** (all in `experiments/007-bigram-scoring/scripts/`):
- `config.py` — shared paths, constants
- `tokenize_corpora.py` — Stage 1: raw corpora → cached token files
- `count_ngrams.py` — Stage 2: token files → n-gram TSVs (raw + normalized)
- `check_coverage.py` — benchmark coverage analysis by type

**How to run** (in devcontainer):
```bash
# Stage 1 — tokenize (slow, ~hours; cached output reusable)
python -m experiments.007-bigram-scoring.scripts.tokenize_corpora \
    --vocab-filter pipelines/trie/outputs/trie_dataset.json

# Stage 2 — count bigrams (fast, ~80s; re-runnable)
python -m experiments.007-bigram-scoring.scripts.count_ngrams

# Coverage check
python -m experiments.007-bigram-scoring.scripts.check_coverage
```

**Key results:**

Corpus size (total bigram occurrences):
| Corpus | Total bigrams | Share |
|--------|--------------|-------|
| wisesight | 355K | 0.3% |
| wongnai | 3.96M | 3.7% |
| prachathai | 53.3M | 50.0% |
| thwiki | 49.3M | 46.0% |

Raw merge dominated by prachathai/thwiki (96%). Added **normalized merge** (equal-weight per corpus) to `count_ngrams.py` — produces both `ngrams_2_merged_raw.tsv` and `ngrams_2_merged.tsv`.

**Output files** (in `experiments/007-bigram-scoring/data/`):
- `tokens_{corpus}.txt` — cached token files (Stage 1 output)
- `ngrams_2_{corpus}.tsv` — per-corpus raw counts
- `ngrams_2_merged_raw.tsv` — raw count sum across corpora
- `ngrams_2_merged.tsv` — normalized equal-weight merge (primary output)

**Coverage on normalized merge:**
| Category | Coverage |
|---|---|
| Bigram expected | 80/110 (72.7%) |
| Compound expected | 53/73 (72.6%) |
| All expected | 133/183 (72.7%) |
| Bigram valid (incl. alternatives) | 299/518 (57.7%) |

Of the 30 missing bigram-type pairs: ~8 are ๆ-repeaters (systematically filtered), ~10 are arguably compound words (potential re-tagging), ~8 genuinely rare, ~4 plausibly in corpora but below min-count.

### Known Issues — Documented

Full analysis in `research/007-bigram-scoring/tokenization-issues.md`:

1. **Number-bridged false bigrams** — `_is_valid_thai_word()` drops numbers without inserting boundaries, creating false adjacencies like (ราคา, บาท)
2. **Under-segmented compound tokens** — newmm produces compounds like ในประเทศ that pass vocab filter
3. **Compound word benchmark tagging** — 73/183 rows tagged as compound; some borderline cases remain
4. **SentencePiece recommendation** — maintainer received external advice to explore data-driven tokenization (BPE/Unigram model) for future iterations

### IME Compound Word Research

Documented in `tokenization-issues.md` Issue 4. Key finding: all major IMEs (Mozc, libkkc, libpinyin, Rime) store both compound words and their decomposed forms, letting Viterbi + language model arbitrate. THAIME should follow the same pattern.

## Next Steps

### Immediate (Phase 3: Smoothing Evaluation)
1. Implement smoothing methods (add-alpha, Kneser-Ney, deleted interpolation)
2. Build a bigram scoring function that takes `(context_word, candidate_word)` → score
3. Evaluate on the 110 bigram-type benchmark rows
4. Compare smoothing methods and interpolation weights

### Before Phase 3 (optional cleanup)
- Maintainer review of v0.1.1 benchmark tagging — a few bigram-tagged rows may need reclassification to compound (สีขาว, ดีไหม, มีแต่, วิบากกรรม, etc.)
- These are rows where `context + expected_top` is a compound word but wasn't in the trie vocab

### Later
- Fix number-bridged bigrams (insert boundaries at dropped tokens)
- Explore SentencePiece tokenization for better n-gram extraction
- Phase 4: Viterbi integration prototype
- Phase 5: Trigram assessment (if needed)

## File Inventory

```
research/007-bigram-scoring/
    007-bigram-scoring.md       # Research plan (Phase 1-6)
    tokenization-issues.md      # Known issues analysis
    progress.md                 # This file

benchmarks/ranking/bigram/
    v0.1.0.csv                  # Original benchmark (200 rows, no type column)
    v0.1.1.csv                  # Tagged benchmark (added type column)

experiments/007-bigram-scoring/
    scripts/
        config.py               # Shared paths and constants
        tokenize_corpora.py     # Stage 1: corpora → token files
        count_ngrams.py         # Stage 2: token files → n-gram TSVs
        check_coverage.py       # Benchmark coverage analysis
        find_collisions.py      # Phase 1 helper (romanization collisions)
    data/
        tokens_*.txt            # Cached token files (gitignored)
        ngrams_2_*.tsv          # Bigram frequency tables (gitignored)
```
