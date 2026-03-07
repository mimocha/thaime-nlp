# Research 003: Component-Level Romanization — Progress Notes

**Branch:** `research/003-component-romanization`
**Last updated:** 2026-03-07

## Status: Stage 3 (Validation) — In Progress

## What We've Done

### Stage 1: Component Inventory (Complete)

Ran `analyze_word()` from `src/variant_generator.py` on the top 1000 Thai words
(from `pipelines/benchmark-wordconv/output/word_frequencies.csv`).

**Scripts:**
- `experiments/003-component-romanization/01_component_inventory.py` — extracts raw inventory
- `experiments/003-component-romanization/02_prepare_curation.py` — formats for human review

**Key finding:** The syllable decomposition code has bugs (~5% of syllables) caused by:
1. `_parse_g2p_groups()` not splitting on apostrophes in TLTK g2p output (biggest issue)
2. `_split_romanization_by_g2p()` heuristic misalignment
3. `_detect_final_consonant()` missing glide consonants (j/w)
4. Doubled consonants not handled
5. Thai repetition marker ๆ corruption

**Decision:** We chose NOT to fix `analyze_word()` since the component dictionary
will eventually replace the rule-based generator. Instead, we manually curated the
inventory from the noisy output (Option C from the analysis).

**Curated inventory (after manual review):**
- Onsets: 29 valid entries (from 30 raw; removed `-` artifact and `ๆ`)
- Vowels: 16 valid entries (from 87 raw; ~65 were garbage from bad decomposition)
- Codas: 9 valid entries (from 9 raw; removed `c` artifact and `ๆ`)

**Design decision — vowel+glide decomposition:**
Diphthongs like แล้ว (laeo) are decomposed as vowel + coda (ae + w) rather than
atomic vowels (aeo). This matches native speaker typing intuition and generates
both forms via Cartesian product when coda `w → [w, o]` and `y → [y, i]`.
Affected vowels removed from inventory: aeo, io, eo, ui, oei.

### Stage 2: Draft Component Dictionary (Complete)

Dictionary file: `data/dictionaries/component-romanization.yaml`

**Key design decisions made:**
- Keys are RTGS romanization strings (unambiguous, position-independent)
- Onset clusters are atomic entries, not decomposed (noted for future work:
  clusters could be {base} x {h/∅} x {r/l})
- No r/l swap — enforce correct spelling for ร→r and ล→l
- Voicing added to unaspirated stops: k→g, t→d, p→b (onsets and codas)
- ch→[ch, j, sh] — RTGS merges จ and ช; j/sh cross-contamination is accepted tradeoff
- w onset → [w, v]

### Stage 3: Validation Against Benchmark (In Progress)

**Script:** `experiments/003-component-romanization/03_validate_benchmark.py`

Validates against `benchmarks/word-conversion/v0.1.0.csv` (326 unique words, 1311 entries).
Uses fallback to raw TLTK romanization when decomposition produces garbage components.

**Results after four iterations:**

| Metric | Run 1 | Run 2 | Run 3 (cheat sheet) | Run 4 (missed analysis) |
|--------|-------|-------|---------------------|-------------------------|
| Component coverage | 94.8% | 94.8% | 94.8% | 94.8% |
| Benchmark reproduction | 72.2% (947) | 86.0% (1128) | 86.3% (1131) | **89.0% (1167)** |
| Total generated | 2379 | 4091 | 5408 | 5718 |
| Noise ratio | 60.2% | 72.4% | 79.1% | 79.6% |

**Changes in Run 2 (patterns found from missed entry analysis):**
- Added onsets: kw→[kw,gw], khw→[khw,kw]
- Vowel a: added "u" variant (short อำ/อั → u very common)
- Vowel o: added "or" variant (ออ sound, NOT "oo" which is โอ)
- Vowel u: added "uu" variant (long vowel)
- Vowel ue: added "uee" variant (long vowel)
- Vowel ai: added "aai" variant (long diphthong)
- Vowel ao: added "aao" variant (long diphthong)
- Onset ch: added "sh" variant (for ช/ฉ/ฌ)
- Onset w: added "v" variant

**Changes in Run 3 (cross-reference with Thai Romanization Cheat Sheet):**
Cross-referenced dictionary against a comprehensive Reddit survey comparing 8 romanization
systems (McFarland 1944, Haas 1956, AUA 1997, Paiboon 2002+, RTGS, TYT, TLC, T2E).
Source: `research/003-component-romanization/thai-romanization-cheat-sheet.md`

Changes applied:
- Onset t: added "dt" (Paiboon-like convention for ต, primarily medial position)
- Onset p: added "bp" (Paiboon-like convention for ป, primarily medial position)
- Vowel a: added "ah" (TYT system, primarily for long อา)
- Vowel oe: added "uh", "ur" (TLC/T2E/McFarland for /ɤ̞/ vowel)
- Coda w: added "u" (Paiboon convention, /-w/ → -u after i vowel, e.g. /iw/ → iu)

New benchmark matches: +3 entries (all from "ah" variant: "baht", "nahm", "ah").

**Key structural findings from cross-reference:**

1. **จ (/c/) vs ช/ฉ/ฌ (/cʰ/) can be split.** TLTK g2p distinguishes them: `c` for จ,
   `ch` for ช. Currently merged under RTGS "ch". Ideal split:
   - จ → [j, ch] (j primary, ch rare/medial)
   - ช/ฉ/ฌ → [ch, sh, j] (ch/sh primary, j rare)
   Cannot test with current `analyze_word()` — deferred to Phase 2.

2. **ออ (/ɔː/) vs โอ (/o̞ː/) can be split.** TLTK g2p distinguishes them: uppercase
   `O/OO` for ออ, lowercase `o/oo` for โอ. Ideal split:
   - /ɔː/ (ออ) → [o, oh, or, aw]
   - /o̞ː/ (โอ) → [o, oh]
   Cannot test with current `analyze_word()` — deferred to Phase 2.

3. **Paiboon-like "tenuis" forms (dt, bp)** are widely used across learning systems
   (Paiboon, TYT, T2E, Tiger) but not typical of native speaker informal typing.
   Included for IME coverage but noted as primarily medial-position forms.

Decisions NOT to add (maintainer review):
- Long diphthong doubles (iia, uua, euua): deferred — fuzzy trie may handle naturally
- "aw" for /ɔː/: not added — would cross-contaminate /o̞ː/ words in merged entry
- "eu" for /ɤ̞/ (oe): not added — weird per maintainer, already under "ue" for /ɯ/

**Changes in Run 4 (systematic missed entry analysis):**
Categorized all 180 missed entries from Run 3 into 14 categories. See analysis below.

Changes applied:
- Onset tr: added "dr" (voicing, same pattern as kr→gr, pr→br)
- Vowel e: added "ee" (long เอ: ทะเล→talee, เค้ก→keek, ประเทศ→prateed)
- Vowel oe: added "eo" (reordering — both oe/eo needed for /ɤ̞/ vowel)
- Vowel ua: added "uaa" (extra length variant)
- Vowel ai: added "aii" (extra length variant)
- Vowel oi: added "oii" (extra length variant)

New benchmark matches: +36 entries. Best signal-to-noise ratio of any run (+36 matches, +6% variants).

Attempted but reverted:
- Coda t: tried adding "j" for จ-as-coda (อาจ→aj), but this would cross-contaminate
  ALL t-coda words (สวัสดี→sawajdee). Same structural issue as จ/ช onset merge —
  deferred to Phase 2.

Decisions NOT to add (maintainer review):
- r-dropping from clusters (ครับ→kab): declined — คับ is a separate word, not ครับ
- r/l swap (ลอง→rong): declined — enforce correct spelling
- ก็→goo/koo implied vowel: declined — gor/goh already covers it
- ก๋วย onset/vowel boundary: structural decomposition issue, not a dictionary fix

**Missed entry analysis — 180 entries in 14 categories:**

| Category | Count | Action |
|----------|-------|--------|
| A. Loanword English (coffee, japan, etc.) | 7 | Out of scope |
| B. Decomposition fallback (analyze_word bugs) | 42 | Blocked — Phase 2 |
| C. Benchmark typo (ช→c) | 3 | Fix benchmark |
| D. nh/mh prefix (หน/หม structural) | 7 | Deferred — Phase 2 |
| E. oo for /ɔː/ vowel (ออ/โอ merge) | 16 | Deferred — Phase 2 split |
| F. r/l swap | 3 | Declined (enforce spelling) |
| G. Extra vowel length (ua→uaa etc.) | 24 | **Applied (Run 4)** |
| H. English-influenced (you, me, one) | 5 | Out of scope |
| I. oe vowel reorder (เ-ิ→eo) | 11 | **Applied (Run 4)** |
| J. Implied vowel special (ก็) | 5 | Declined |
| K. Onset/vowel boundary (ก๋วย) | 4 | Structural — Phase 2 |
| L. r-dropping from clusters | 15 | Declined (separate words) |
| M. Cluster voicing (tr→dr) | 1 | **Applied (Run 4)** |
| N. ee for short เ vowel | 13 | **Applied (Run 4)** |
| O. ai variant (อะไร→alai) | 2 | Benchmark error (r/l swap) |
| P. จ coda as j (อาจ→aj) | 3 | Structural — Phase 2 |
| Q. Long diphthong forms | 7 | Partial (aii, oii applied) |
| R. Other vowel spelling alts | 12 | Mixed — reviewed case by case |

## What's Left To Do

### Remaining Stage 3 work

1. **Remaining 144 missed entries** — now fully categorized (see Run 4 analysis above).
   The remaining misses break down as:
   - 42 blocked by decomposition bugs (23%)
   - 23 deferred to Phase 2 (nh/mh, oo-for-/ɔː/, จ-coda-as-j) (13%)
   - 12 out of scope (loanwords, English homophones) (7%)
   - 18 declined by maintainer (r-dropping, r/l swap, ก็) (10%)
   - 3 benchmark typos to fix (ช→c)
   - ~46 remaining edge cases (vowel alts, long diphthongs, structural)

2. **Decide when to stop iterating** — At 89.0%, we're close to the 90% target.
   The remaining 1% gap is mostly structural issues that the dictionary can't fix:
   decomposition bugs, RTGS merges, and onset/vowel boundary ambiguities. Further
   dictionary refinement has diminishing returns. Recommendation: **stop iterating
   and move to Stage 4 (Summary)**, noting that Phase 2's new generator should
   close the remaining gap.

3. **Noise ratio (79.6%)** — still high, but stabilized between Run 3 and Run 4.
   The over-inclusive strategy adds learner-system coverage at the cost of noise.
   Phase 2's ออ/โอ and จ/ช splits should reduce noise by eliminating cross-contamination.

### Known issues not yet addressed

- **nh/mh prefix for หนำ words** (หน้า→nha, หมด→mhod): structural issue where
  ห-leading words have an onset that doesn't map cleanly to a single component.
  Deferred as future refinement.
- **Loanword spellings** (coffee, japan, beer, cake, ok): out of scope per plan.
- **Decomposition bugs** (21 fallback words, 5% of syllables): not fixing
  `analyze_word()` in this research. These words only get base TLTK romanization.
- **Short/long vowel distinction**: dictionary doesn't distinguish, so variants
  like "aa" can over-generate for short vowels and "u" can over-generate for
  long vowels. Noted for future refinement.
- **จ/ช merge** and **ออ/โอ merge**: RTGS-keyed dictionary merges these pairs.
  TLTK g2p CAN distinguish them. Phase 2 should key on g2p symbols directly.
  See dictionary comments for ideal split variant sets.

### Stage 4: Summary

Write final `research/003-component-romanization/summary.md` with:
- Validated dictionary (reference to `data/dictionaries/component-romanization.yaml`)
- Final coverage metrics
- Edge case catalog
- Recommendations for next phase

## File Inventory

| File | Description |
|------|-------------|
| `research/003-component-romanization/plan.md` | Research plan |
| `research/003-component-romanization/progress.md` | This file |
| `data/dictionaries/component-romanization.yaml` | The component dictionary (deliverable) |
| `experiments/003-component-romanization/01_component_inventory.py` | Stage 1 extraction script |
| `experiments/003-component-romanization/02_prepare_curation.py` | Stage 1 curation formatter |
| `experiments/003-component-romanization/03_validate_benchmark.py` | Stage 3 validation script |
| `experiments/003-component-romanization/output/` | All intermediate outputs (gitignored) |
