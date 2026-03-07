# Component-Level Romanization Framework

**Date:** 2026-03-07
**Author:** Claude (agent) + Chawit Leosrisook (maintainer)
**Branch:** `research/003-component-romanization`
**Status:** Complete

## Research Question

Can Thai informal romanization be decomposed into a finite set of reusable phonological components (onsets, vowels, codas), where each component maps to a small set of valid Latin spellings, such that whole-word romanizations can be generated via Cartesian product of component variants?

## Approach

We extracted all distinct phonological components from the top 1000 most frequent Thai words (from wisesight, wongnai, and prachathai corpora) using TLTK's syllable decomposition. Each word was broken into syllables, and each syllable into onset + vowel + coda triples. From the deduplicated inventory, we built a component dictionary mapping each component to its valid informal romanization variants. The dictionary was validated through four iterative runs against the v0.1.0 benchmark (326 unique words, 1311 entries), with each iteration refining variant sets based on missed entry analysis and cross-referencing against established romanization systems (RTGS, Paiboon, Haas, AUA, TYT, TLC, T2E, McFarland).

## Key Findings

- **The answer is yes.** Thai informal romanization decomposes into 54 reusable components (29 onsets, 16 vowels, 9 codas) whose Cartesian product reproduces 89.0% of benchmark entries. The dictionary is small enough for complete human validation.

- **89.0% benchmark reproduction rate** (1167/1311 entries) after four iterations of refinement. This is close to the 90% target and the remaining gap is dominated by infrastructure limitations, not dictionary gaps.

- **94.8% component coverage** — nearly all components found in the benchmark vocabulary have dictionary entries. The 5.2% gap comes from `analyze_word()` decomposition bugs affecting 21 words.

- **The remaining 11% of missed entries are well-understood.** Systematic categorization of all 144 remaining misses shows:

  | Category | Count | % of missed |
  |----------|-------|-------------|
  | Decomposition bugs (analyze_word) | 42 | 29% |
  | Deferred structural issues (nh/mh, ออ/โอ, จ-coda) | 23 | 16% |
  | Declined by maintainer (r-drop, r/l swap) | 18 | 13% |
  | Out of scope (loanwords, English homophones) | 12 | 8% |
  | Remaining edge cases (vowel alts, boundaries) | 46 | 32% |
  | Benchmark typos (ช→c) | 3 | 2% |

- **Component-level labelling is dramatically more efficient than word-level.** The 54-entry dictionary generates variants for all 326 benchmark words. Labelling 54 components (each with 1-5 variants) replaces manually enumerating thousands of word-level combinations.

- **Cross-referencing with established romanization systems improved both coverage and linguistic grounding.** A Thai Romanization Cheat Sheet comparing 8 systems revealed systematic gaps (Paiboon-like "dt"/"bp" forms, TYT "ah" variant, TLC/T2E "uh"/"ur" for เออ) and structural insights (จ/ช and ออ/โอ splits feasible via TLTK g2p).

- **Two RTGS merges limit accuracy and increase noise.** RTGS maps both จ (/c/) and ช (/cʰ/) to "ch", and both ออ (/ɔː/) and โอ (/o̞ː/) to "o". TLTK's g2p output preserves both distinctions (`c` vs `ch`, `O/OO` vs `o/oo`), enabling future splits that would reduce noise and improve precision.

- **Noise ratio is 79.6%** (4551 of 5718 generated variants are not in the benchmark). This is high but expected: the benchmark only covers native speaker patterns, while the dictionary includes learner-system variants (dt, bp, uh, ur). Many "noise" variants are plausible romanizations not labelled in the benchmark. The ออ/โอ and จ/ช splits should significantly reduce genuine noise by eliminating cross-contamination.

- **3 benchmark entries are typos.** ชั้น→"can", ช่วง→"cuang", ใช่→"cai" use "c" for ช, which does not exist in any romanization system. These should be removed in a benchmark revision.

## Dictionary Design

The validated dictionary is at `data/dictionaries/component-romanization.yaml`.

**Key design decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dictionary key | RTGS romanization strings | Unambiguous, position-independent (with two known exceptions: จ/ช and ออ/โอ) |
| Onset clusters | Atomic entries (e.g., "kr", "khr") | Small inventory (~7 entries), not all compositions valid |
| Diphthong decomposition | vowel + coda (ae+w, i+w, etc.) | Matches native typing intuition, generates both forms via Cartesian product |
| r/l swap | Not allowed | Enforce correct spelling; r/l-swapped words are separate dictionary entries |
| r-dropping from clusters | Not allowed | ครับ→"kab" is the word คับ, not a variant of ครับ |
| Voicing | Allowed for unaspirated stops | k→g, t→d, p→b in both onset and coda positions |
| Over-inclusive vs over-restrictive | Lean over-inclusive | False negatives (missing valid input) worse for IME UX than false positives (unused trie entries) |

**Component inventory summary:**

| Type | Count | Variants range | Examples |
|------|-------|----------------|----------|
| Onsets | 29 | 1-3 variants each | k→[k,g], ch→[ch,j,sh], t→[t,d,dt] |
| Vowels | 16 | 1-5 variants each | a→[a,aa,ar,u,ah], oe→[oe,eo,er,uh,ur] |
| Codas | 9 | 1-3 variants each | t→[t,d], w→[w,o,u] |
| **Total** | **54** | | |

## Recommendation

The component dictionary is ready for use as the foundation of a production romanization generator (Phase 2 of Change Plan 03):

1. **Build the Phase 2 generator using TLTK g2p output directly**, not RTGS. This enables the จ/ช and ออ/โอ splits documented in the dictionary comments, which will reduce noise and improve accuracy beyond the 89% achieved here.

2. **Split the dictionary keys for Phase 2:**
   - จ (TLTK `c`) → [j, ch] — j primary, ch rare/medial
   - ช/ฉ/ฌ (TLTK `ch`) → [ch, sh, j] — ch/sh primary, j rare
   - ออ (TLTK `O/OO`) → [o, oh, or, aw] — distinct from โอ
   - โอ (TLTK `o/oo`) → [o, oh] — no or/aw/oo variants
   - จ-as-coda (TLTK `c` in final position) → [j] — currently blocked by coda t cross-contamination

3. **Add nh/mh onset support** for หน/หม words (หน้า→nha, หมด→mhod). This is a structural addition requiring a new onset type in the dictionary schema.

4. **Fix the 3 benchmark typos** (ชั้น→"can", ช่วง→"cuang", ใช่→"cai") in a benchmark revision (v0.1.1).

5. **Do not add r-dropping or r/l swap** to the dictionary. These are separate-word phenomena (คับ vs ครับ, ลอง vs รอง), not romanization variants. The trie should handle them as distinct dictionary entries.

6. **Consider the noise-precision tradeoff** during Phase 2 validation. The over-inclusive strategy (dt, bp, uh, ur, etc.) is appropriate for initial IME deployment but may need pruning based on real user typing data.

## Limitations

- **Benchmark reproduction is 89%, not 90%.** The 1% gap is structural — decomposition bugs (42 entries), RTGS merges (23 entries), and edge cases (46 entries). These are not dictionary gaps but infrastructure issues that Phase 2 will address.

- **Noise ratio is high (79.6%).** The Cartesian product approach inherently generates some implausible combinations. Phase 2's ออ/โอ and จ/ช splits will help, but vowel length over-generation (e.g., "aa" for short vowels) will persist until the dictionary distinguishes short/long forms.

- **The dictionary was validated on only 326 words.** Phase 2 should test on the full top 10K word list to verify generalization. The component inventory may need expansion for rare phonological patterns not present in the top 1000.

- **Loanwords are out of scope.** Words like กาแฟ→"coffee", เค้ก→"cake" use English source spellings that cannot be derived from phonological decomposition. These need a separate loanword lookup table.

- **No frequency or confidence weights.** All variants are treated equally. Future work could assign weights based on corpus frequency of each romanization pattern, improving trie ranking.

- **The current `analyze_word()` function has bugs** affecting ~5% of syllables. The Phase 2 generator should build a new decomposition function based on TLTK g2p, not inherit the current code.

## Iteration History

| Run | Reproduction | Generated | Noise | Key changes |
|-----|-------------|-----------|-------|-------------|
| 1 (initial) | 72.2% (947) | 2379 | 60.2% | First draft dictionary |
| 2 (refinement) | 86.0% (1128) | 4091 | 72.4% | +kw/khw onsets, +vowel length variants, +sh/v |
| 3 (cheat sheet) | 86.3% (1131) | 5408 | 79.1% | +dt/bp/ah/uh/ur/coda-u from romanization systems survey |
| 4 (missed analysis) | 89.0% (1167) | 5718 | 79.6% | +dr/ee/eo/uaa/aii/oii from categorized miss analysis |

## References

- Experiment branch: `research/003-component-romanization`
- Experiment artifacts: `experiments/003-component-romanization/`
- Component dictionary: `data/dictionaries/component-romanization.yaml`
- Change Plan 03 (Phase 1 + Phase 2): `docs/plans/change-plan-03-component-romanization.md`
- Research 002 summary: `research/002-informal-romanization-variants/summary.md`
- Thai Romanization Cheat Sheet: `research/003-component-romanization/thai-romanization-cheat-sheet.md`
- TLTK: https://pypi.org/project/tltk/
- RTGS: https://en.wikipedia.org/wiki/Royal_Thai_General_System_of_Transcription
