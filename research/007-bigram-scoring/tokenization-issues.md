# Tokenization & Compound Word Issues in N-gram Extraction

**Topic:** research/007-bigram-scoring
**Date:** 2026-03-13
**Author:** Claude (agent) + Chawit Leosrisook (maintainer)
**Context:** Phase 2 (n-gram extraction) revealed several tokenization issues that affect bigram quality. This document catalogs the issues, analyzes their impact, and records recommendations for future iterations.

## Issue 1: Number-Bridged False Bigrams

### Description

`_is_valid_thai_word()` silently drops non-Thai tokens (numbers, punctuation, Latin text) during tokenization. When a number appears between two Thai words, dropping it creates a false adjacency — the two words appear as a bigram even though they were never adjacent in the original text.

### Examples

| Original text | After tokenization | False bigram |
|---|---|---|
| ราคา 500 บาท | ราคา บาท | (ราคา, บาท) |
| วันที่ 15 พฤศจิกายน | วันที่ พฤศจิกายน | (วันที่, พฤศจิกายน) |

### Impact

These false bigrams inflate counts for word pairs that co-occur around numbers (prices, dates, quantities). In the ranking model, this could cause spurious context signals — e.g., predicting บาท after ราคา even when the user hasn't typed a number yet.

### Fix

In `tokenize_text()`, insert a sequence boundary (blank line in the token file) wherever a non-Thai token was removed, rather than silently dropping it. This preserves the true adjacency structure.

**Severity:** Low-medium. Affects a subset of bigrams, mostly around numeric patterns. Does not block initial scoring model evaluation.

---

## Issue 2: Under-Segmented Compound Tokens in Trie Vocabulary

### Description

PyThaiNLP's `newmm` tokenizer sometimes produces compound tokens that arguably should be segmented further. When these compounds exist in the trie vocabulary, they pass the `--vocab-filter` and appear as single tokens in the n-gram data.

### Examples

| newmm output | Expected segmentation |
|---|---|
| ในประเทศ | ใน + ประเทศ |
| เกี่ยวกับ | เกี่ยว + กับ |

The token `ในประเทศ` then forms bigrams like `(ในประเทศ, ไทย)` ranked #117 in the normalized merge — when the more useful signal would be `(ประเทศ, ไทย)`.

### Impact

Creates bigrams at the wrong granularity. The scoring model learns associations between compound tokens that the Viterbi decoder may not produce if it segments differently at runtime.

### Fix

This is a trie vocabulary curation issue, upstream of the n-gram pipeline. The compound entries should be reviewed and either:
- Removed from the trie (forcing decomposition), or
- Accepted as valid single tokens (in which case the bigram is correct at that granularity)

The trie pipeline's `_decompose_compounds()` function already handles some of these, but the threshold (`_DECOMPOSE_MIN_CHARS = 10`) may be too conservative.

**Severity:** Low. Affects a small number of high-frequency bigrams. The underlying data is still usable.

---

## Issue 3: Compound Words vs Bigrams in the Benchmark

### Description

Of the 183 context-dependent rows in the ranking benchmark (`v0.1.0.csv`), **73 rows (40%)** have `context + expected_top` concatenated into a string that exists as a single entry in the trie vocabulary. This means these "bigrams" may actually be single compound words that the tokenizer and lattice treat as one unit.

### Analysis

The 73 cases fall into several subcategories:

**Category A: True compound words (~30 cases)**
The compound has a distinct meaning not derivable from its parts, or is lexicalized as a single unit in standard Thai dictionaries.

Examples: ป้องกัน (protect), เครือข่าย (network), แตกต่าง (differ), เลือกตั้ง (elect), กลไก (mechanism), อื้อฉาว (scandalous), เติบโต (grow up), ตอบโต้ (retaliate)

These are analogous to English words like "understand" — no one thinks of "under" + "stand."

**Category B: Common collocations (~25 cases)**
High-frequency word pairs that are often stored as dictionary entries but whose component words are independently meaningful.

Examples: กินข้าว (eat rice), ต้นไม้ (tree), ปีใหม่ (new year), ตอนเช้า (morning), คนไทย (Thai person), เสื้อผ้า (clothing), ห้องพัก (room)

These are the ambiguous cases. Thai speakers would recognize both the compound and the individual words.

**Category C: Repeater forms (ๆ) (~8 cases)**
Examples: เก่าๆ, ต่างๆ, ขำๆ, ไทยๆ

Maiyamok (ๆ) is filtered by `_is_valid_thai_word()`, so these bigrams never appear in the n-gram data. They are systematically untestable with the current pipeline.

**Category D: Miscellaneous (~10 cases)**
Proper nouns, loanwords, and edge cases: บึงกุ่ม (district name), มัทฉะ (matcha), ปะป๊า (dad, colloquial — contains filtered tone mark ๊)

### Impact on Benchmark Evaluation

For bigram coverage evaluation, the 73 compound rows should be excluded or tagged. The effective coverage of the bigram frequency table should be measured against the ~110 non-compound rows only.

Reported coverage on the normalized merged bigram table:
- All 183 context rows: 133/183 = **72.7%**
- Excluding 73 compound rows (~110 rows): coverage is higher (exact number pending re-evaluation with tagging)

### Recommendation

For the v0.1.1 benchmark:
1. **Tag** compound rows with a `compound` flag rather than removing them
2. Report bigram coverage metrics separately for compound vs non-compound rows
3. The compound rows remain valid test cases for the full Viterbi system (which considers both compound and decomposed lattice paths), just not for the bigram scoring component in isolation

---

## Issue 4: The Compound Word Problem in IME Design

### How Other IMEs Handle This

Research into Mozc, libkkc, libpinyin, libime, and Rime reveals a **universal approach**:

1. **Dictionary stores both compounds AND components** — redundantly, by design
2. **Lattice construction creates parallel paths** — both `[กินข้าว]` (single node) and `[กิน]+[ข้าว]` (two nodes) exist as candidate paths
3. **Viterbi + language model picks the winner** — no hard-coded preference for longest match

The compound entry tends to win in practice because:
- It has a favorable corpus-derived emission cost
- The single-node path avoids accumulating transition costs between morphemes

### Implications for THAIME

The current trie vocabulary contains many compound words that overlap with their decomposed forms. This is **not a bug** — it's standard IME design. The Viterbi decoder's lattice should naturally contain both paths, and the scoring model (unigram cost + bigram transition cost) arbitrates.

However, this means:
- The **bigram model** is only relevant for the decomposed path — it fires when the lattice chose `[กิน]+[ข้าว]`, not when it chose `[กินข้าว]`
- The **benchmark** should test both scenarios but report them separately
- Aggressive compound decomposition (removing all compounds from the dictionary) would reduce candidate count but lose useful signal

### The Non-Compositional Compound Problem

A naive frequency-based decomposition rule ("decompose if parts are more frequent than the whole") fails on non-compositional compounds:

| Compound | Meaning | Parts | Part meanings |
|---|---|---|---|
| แม่น้ำ | river | แม่ + น้ำ | mother + water |
| ลูกตา | eyeball | ลูก + ตา | child + eye |
| หัวใจ | heart | หัว + ใจ | head + mind |

If we decompose แม่น้ำ, the bigram (แม่, น้ำ) gets artificially inflated, and the model incorrectly predicts น้ำ after แม่ in contexts where the user means "mother," not "river."

This is a known problem in NLP. The correct solution is **not** to make a binary keep/remove decision per compound, but to let the probabilistic model evaluate both paths in context — which is exactly what the Viterbi lattice does.

---

## Future Direction: Subword Tokenization (SentencePiece)

### Recommendation from External Consultation

The maintainer received a recommendation to explore **SentencePiece** and other data-driven tokenization methods for the n-gram extraction pipeline. The rationale:

> Even for our v1 thaime engine release, we can use deep learning as part of the research and data generation pipeline; separate from the engine itself.

### Background

The traditional approach (PyThaiNLP `newmm`) uses dictionary-based maximum matching — the tokenizer must have an explicit vocabulary, and compound/bigram boundaries are dictated by what's in the dictionary.

Modern NLP has largely moved to **subword tokenization** (BPE, WordPiece, Unigram Language Model) via tools like SentencePiece:

- **Data-driven**: learns statistically optimal token boundaries from raw corpus text, no dictionary needed
- **Language-agnostic**: treats raw text (including spaces) as a character sequence — designed for unsegmented languages like Thai, Chinese, Japanese
- **Configurable granularity**: target vocabulary size controls how aggressively compounds are decomposed
- **Solves the compound problem**: SentencePiece's Unigram model (Kudo, 2018) iteratively evaluates whether removing a token from the vocabulary hurts corpus likelihood — tokens that are better explained by their parts get pruned, while non-compositional compounds survive

### How SentencePiece Relates to Our Pipeline

The current pipeline's compound decomposition approach (Issue 3) is effectively a greedy, frequency-based version of the Unigram Language Model algorithm. SentencePiece would formalize this:

1. Train a SentencePiece model on the raw Thai corpora (wisesight, wongnai, prachathai, thwiki)
2. Tokenize the corpora using the trained model (consistent segmentation)
3. Count bigrams on the SentencePiece-tokenized output
4. The resulting bigrams would have consistent, data-driven boundaries

### Tradeoffs

| Aspect | PyThaiNLP newmm (current) | SentencePiece |
|---|---|---|
| Token boundaries | Dictionary-defined, linguistically motivated | Data-driven, statistically optimal |
| Compound handling | Depends on dictionary inclusion | Automatically resolved by corpus statistics |
| User-facing tokens | Always real Thai words | May include subword fragments (e.g., `▁กิน`, `ข้าว`) |
| Consistency | Depends on dictionary version | Deterministic from trained model |
| Setup complexity | Already integrated | Requires training step, new dependency |

### Key Consideration for THAIME

The THAIME engine's trie vocabulary defines the lattice nodes — users see real Thai words as candidates, not subword fragments. So SentencePiece would be used **only in the research/data pipeline** for extracting better n-gram statistics, not in the engine itself.

The approach would be:
1. Train SentencePiece on raw corpora
2. Use it to tokenize corpora for n-gram counting
3. Map the resulting n-grams back to the trie vocabulary for scoring
4. The engine still uses the existing trie + Viterbi architecture

### Status

Noted as a potential improvement for a future iteration. The current PyThaiNLP-based pipeline is sufficient for the initial bigram scoring evaluation (Phase 3). SentencePiece exploration could be a standalone research topic or an enhancement to the n-gram extraction pipeline.

---

## Summary of Action Items

| Issue | Severity | Action | When |
|---|---|---|---|
| 1. Number-bridged bigrams | Low-medium | Insert boundaries at dropped tokens | Next pipeline iteration |
| 2. Under-segmented compounds | Low | Review trie vocabulary decomposition threshold | Trie pipeline update |
| 3. Benchmark compound tagging | Medium | Tag 73 compound rows in v0.1.1 benchmark | Now (before Phase 3) |
| 4. SentencePiece exploration | Low (enhancement) | Consider as standalone research or pipeline upgrade | Future research topic |
