# Change Plan 09: Loanword Vocabulary Expansion

**Date:** 2026-04-12
**Author:** Chawit Leosrisook (maintainer) + Claude (agent)
**Repo:** `mimocha/thaime-nlp`
**Branch:** `pipeline/loanwords`
**Status:** Draft

## Objective

Identify loanwords in the existing vocabulary, generate dual romanization keys (English source spelling + Thai-pronunciation romanization) for each, and integrate them into the trie pipeline as enriched entries. This addresses one of the two largest vocabulary gaps in THAIME: users typing loanwords by their English source spelling (e.g., typing "coffee" for กาแฟ, "taxi" for แท็กซี่) currently get no results.

## Context

Research 001 identified the loanword gap: no programmatic romanization source produces English source spellings from Thai phonological romanization. The variant generator (CP04) cannot produce "coffee" from กาแฟ's onset/vowel/coda decomposition — these are fundamentally different romanization strategies. Research 001 also validated PyThaiNLP's `lookup` engine as the best existing automated source for loanword mappings, though it covers only a subset.

The current pipeline (CP05) processes all words uniformly through TLTK romanization + variant generation. Loanwords receive only Thai-pronunciation romanizations (e.g., กาแฟ → "kafae", "gafae"), missing the English source forms that users actually type.

### Scope

This plan covers identification and romanization of loanwords within the existing vocabulary. It does NOT cover names (see CP10) or expansion of the vocabulary itself (i.e., adding new Thai words not already in the frequency data).

## Approach

### Phase 1: Loanword Identification

Extract candidate loanwords from the current merged vocabulary (~17K words after CP07 filtering) using three complementary methods:

**Method A — PyThaiNLP `lookup` engine:**
Run every word in the vocabulary through PyThaiNLP's `lookup` engine. When `lookup` returns a recognizable English/Latin word (not a `royin`-style romanization), flag the Thai word as a likely loanword. The key heuristic for distinguishing a genuine loanword lookup from a `royin` fallback: if the output contains no Thai-phonetic patterns (no "kh", "ph", "th" clusters, no doubled vowels) and looks like a plausible English/foreign word, it's likely a real loanword mapping.

**Method B — LLM classification:**
For words not caught by Method A, use an LLM (Claude via API, or Bedrock with existing AWS credits) to classify whether each word is a loanword. Prompt structure: given a Thai word and its TLTK romanization, determine if the word is borrowed from English or another foreign language, and if so, provide the source-language spelling. Cache results aggressively (same pattern as CP07's LLM filter).

**Method C — Manual review:**
The maintainer reviews the combined output of Methods A and B, correcting misclassifications and adding missed loanwords. An overrides file (`data/overrides/loanwords.yaml`) allows manual additions and corrections.

### Phase 2: Dual Romanization Generation

For each confirmed loanword, generate two types of romanization keys:

1. **English source spelling** — the word as it would be typed in English (e.g., "coffee", "taxi", "internet"). This comes from PyThaiNLP `lookup`, LLM output, or manual entry. Assign high confidence (0.9) since this is exactly what the user intends to type.

2. **Thai-pronunciation romanization** — the standard pipeline output (TLTK + variant generator). These already exist from CP05. Keep them at their existing confidence weights.

Both key types index to the same Thai word entry in the trie, so typing either "coffee" or "kafae" produces กาแฟ as a candidate.

### Phase 3: Pipeline Integration

Integrate loanword enrichment as a post-processing step in the trie pipeline, after variant generation and before trie export:

```
Word List Assembly
    │
    ▼
TLTK Romanization + Variant Generation  (existing CP05)
    │
    ▼
Loanword Enrichment  ◄── NEW STEP
    │  - Load loanword mappings (Methods A+B+C output)
    │  - Add English source spelling as additional romanization key
    │  - Preserve existing Thai-pronunciation keys
    │
    ▼
Trie Export (trie_dataset.json)
```

The loanword mappings are stored in a standalone file (`data/loanwords/loanword-mappings.yaml` or similar) that can be updated independently of the main pipeline. Format:

```yaml
# data/loanwords/loanword-mappings.yaml
- thai: กาแฟ
  source_lang: english
  source_spelling: coffee
  method: pythainlp_lookup  # or llm, manual
  confidence: 0.9

- thai: แท็กซี่
  source_lang: english
  source_spelling: taxi
  method: pythainlp_lookup
  confidence: 0.9
```

### Phase 4: Validation

Validation is primarily qualitative — the maintainer tests loanword inputs in the CLI/TUI and checks that expected candidates appear. Additionally:

- Count: how many loanwords were identified out of ~17K vocabulary? (Expected: 500–2000)
- Coverage spot-check: manually test 50 common loanwords (from tech, food, brand, and everyday categories) and verify the English source spelling produces the correct Thai candidate.
- Noise check: verify that adding English source keys doesn't create false collisions (e.g., "line" matching both ไลน์ the app and a hypothetical Thai word).

## Corpus Representativeness Concern

The current corpora (Prachathai, Wisesight, Wongnai, Thai Wikipedia) have known blind spots for loanword coverage:

- **Well-covered:** food loanwords (Wongnai), news/political loanwords (Prachathai), general vocabulary loanwords (Wikipedia)
- **Under-covered:** tech jargon (คอนเทนเนอร์, ดีพลอย, เซิร์ฟเวอร์), recent cultural imports (สตรีม, คอนเทนต์, มีม), brand names used as common nouns (ไลน์, แกร็บ)
- **Essentially missing:** very new loanwords that postdate the corpus collection

This plan does NOT attempt to fix corpus representativeness. Instead, it enriches existing vocabulary entries with English source romanizations. Expanding the vocabulary itself (adding new loanwords not in the frequency data) is deferred — the overrides file can handle a small number of manually added high-priority words, but systematic vocabulary expansion requires either new corpus data or a dedicated effort.

## Acceptance Criteria

- Qualitative: the maintainer judges that common loanwords produce correct candidates when typed by English source spelling in the CLI/TUI
- The loanword mappings file is committed, human-readable, and manually editable
- The pipeline runs cleanly with loanword enrichment enabled
- Existing (non-loanword) romanization behavior is unchanged — this is a pure addition of new romanization keys, not a modification of existing ones

## Task Breakdown

| Task | Description | Effort |
|------|-------------|--------|
| T1 | Run PyThaiNLP `lookup` on full vocabulary, extract candidate loanwords | 0.5 day |
| T2 | Build LLM classification prompt + cache infrastructure (reuse CP07 pattern) | 1 day |
| T3 | Run LLM classification on uncovered vocabulary | 0.5 day |
| T4 | Maintainer review of combined loanword list + overrides file | 1 day |
| T5 | Implement pipeline integration (loanword enrichment step) | 1 day |
| T6 | Validation: spot-check 50 loanwords in CLI/TUI | 0.5 day |
| T7 | Documentation: update pipeline docs, add loanword-mappings format spec | 0.5 day |

**Total estimated effort:** ~5 days

## Limitations

- Coverage is bounded by the existing vocabulary. Loanwords not in the frequency data (because they're absent from all four corpora) will not be identified or enriched. The overrides file provides a manual escape hatch for high-priority additions.
- LLM classification may have false positives (marking a native Thai word as a loanword) or false negatives (missing an actual loanword). The manual review step is essential.
- Brand names that function as common verbs/nouns in Thai (e.g., "line" for messaging, "grab" for ride-hailing) may be ambiguous — the English spelling is also a common English word with different meaning. These need manual attention.
- No frequency or popularity data exists for loanword English spellings vs. Thai-pronunciation romanizations. The fixed confidence of 0.9 for English source spellings is a guess. Real user data would improve this.
- Some loanwords have multiple valid English source spellings (e.g., โยเกิร์ต could be "yogurt" or "yoghurt"). The plan handles this by allowing multiple source spellings per entry.

## Open Questions

1. **Should loanword English spellings be case-insensitive?** Currently the trie is case-insensitive (all input lowercased). English source spellings like "iPhone", "WiFi", "COVID" have conventional capitalization that would be lost. This is probably fine — users type lowercase — but worth noting.

2. **Should we include transliterated forms from non-English source languages?** Some Thai loanwords come from Japanese (ซูชิ → "sushi"), Korean (คิมจิ → "kimchi"), or French (กาเฟ่ → "café"). The same approach applies, but LLM classification would need to identify the source language. Consider handling these in the same pass.

3. **How to handle loanwords with Thai-specific semantic drift?** Some borrowed words have shifted meaning in Thai (e.g., เบียร์ covers all beer, not just specific brands). The English source spelling still maps correctly; this is a documentation concern, not a technical one.

## References

- Research 001: Romanization Source Audit — `research/001-romanization-source-audit/summary.md`
- Research 002: Informal Romanization Variants — `research/002-informal-romanization-variants/summary.md`
- Change Plan 05: Trie Pipeline — `docs/plans/change-plan-05-trie-pipeline.md`
- Change Plan 07: Trie Quality — `docs/plans/change-plan-07-trie-quality.md`
- PyThaiNLP documentation: https://pythainlp.github.io/
- PyThaiNLP `lookup` engine: validated in Research 001 for loanword mappings
