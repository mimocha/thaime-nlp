# Change Plan 10: Names Corpus Integration

**Date:** 2026-04-12
**Author:** Chawit Leosrisook (maintainer) + Claude (agent)
**Repo:** `mimocha/thaime-nlp`
**Branch:** `pipeline/names`
**Status:** Draft

## Objective

Integrate Thai names (first names, surnames, and nicknames) into the trie pipeline as a top-level corpus alongside the existing text corpora (thwiki, prachathai, wisesight, wongnai). This addresses the second largest vocabulary gap in THAIME: Thai personal names are almost entirely absent from the current dictionary, so typing a romanized name produces no candidates.

## Context

Names are fundamentally different from general vocabulary in two ways that affect pipeline design:

1. **No natural frequency signal.** Text corpora provide word frequency from usage counts. Name lists are flat inventories — every name appears exactly once in the source data, with no indication of popularity. The pipeline must handle this gracefully rather than dismissing names as noise.

2. **Romanization is a personal choice.** For regular Thai words, romanization follows phonological rules (even if informally). For names, individuals choose their own romanization, often inconsistently (ณัฐ → "Nat", "Nath", "Natt", "Nutch"). The component romanization pipeline will generate plausible romanizations but cannot predict any specific person's chosen spelling. User dictionary is the architectural answer for personal-spelling gaps.

### Why a top-level corpus?

If names are injected into the existing pipeline without special treatment, most will be filtered out: they appear zero times in text corpora, have no cross-corpus support, and fall below minimum frequency thresholds. Treating names as a separate corpus with its own weight in the frequency normalization formula means:

- Names get a baseline frequency floor that keeps them in the vocabulary
- The corpus weight parameter controls how strongly names compete with common vocabulary (tunable)
- Pipeline filters (minimum count, multi-source requirement) can be adjusted or bypassed for the names corpus specifically

## Data Sources

### Phase 1 Sources (freely available, immediate use)

**Source A — thai-names-corpus (GitHub, CC-BY 4.0):**
https://github.com/korkeatw/thai-names-corpus

Contains text files of Thai family names, female first names, and male first names, all in Thai script. No romanization included — our pipeline generates romanizations. CC-BY 4.0 license is compatible with THAIME's MPL-2.0.

Characteristics:
- Easy to parse (plain text, one name per line)
- Names in Thai script only — romanization must be generated
- TLTK word decomposition may struggle with some names (names often contain rare character combinations or don't decompose into standard syllable patterns)
- Size: expected hundreds to low thousands of entries per file

### Phase 2 Sources (require owner permission, added incrementally)

**Source B — Behind the Name (web, permission required):**
https://www.behindthename.com/submit/names/usage/thai

Hand-curated collection of Thai names with romanization attached. High-quality data with both Thai script and Latin spelling. Paginated web interface — extraction requires scraping or a data request to the owner.

Copyright: https://www.behindthename.com/info/copyright — maintainer will email the owner to request permission and potentially the dataset itself. If permission is denied, this source is dropped.

**Source C — thai-language.com (web, permission required):**
http://www.thai-language.com

Three relevant pages with Thai spellings, pronunciations, and romanization:
- Foreign names in Thai: http://www.thai-language.com/id/589838
- Thai first names: http://www.thai-language.com/id/589844
- Thai nicknames: http://www.thai-language.com/id/589843

Contact: glenn@thai-language.com — maintainer will email for permission. If permission is denied, this source is dropped.

### Phase staging rationale

Phase 1 (Source A) is immediately usable with no legal uncertainty. The pipeline should be built and tested with this source first. Phase 2 sources are added only if and when permission is granted. The architecture must support incremental addition of new name sources without restructuring.

## Approach

### Phase 1: Names Corpus Infrastructure

**Task 1.1 — Corpus directory structure:**

Create a names corpus directory following the existing corpus conventions:

```
data/
├── corpora/
│   ├── thwiki/
│   ├── prachathai/
│   ├── wisesight/
│   ├── wongnai/
│   └── names/              ◄── NEW
│       ├── README.md        # Source attribution, license, provenance
│       ├── raw/             # Original downloaded files
│       │   └── thai-names-corpus/
│       ├── processed/       # Cleaned, deduplicated name lists
│       │   ├── first_names.txt
│       │   ├── surnames.txt
│       │   └── nicknames.txt  (if available)
│       └── frequency.tsv    # name → count (uniform: all 1)
```

**Task 1.2 — Name ingestion script:**

Write `scripts/ingest-names.py` (or add to existing pipeline) that:
1. Downloads/copies the thai-names-corpus files
2. Deduplicates across files (some names may appear as both first name and surname)
3. Validates entries are valid Thai text (filter any non-Thai characters, empty lines)
4. Produces `frequency.tsv` with uniform count of 1 for every name
5. Records provenance metadata in `README.md`

**Task 1.3 — Pipeline filter adjustments:**

The existing pipeline filters (from CP05/CP07) will reject most names because they:
- Appear in only 1 corpus (the names corpus)
- Have a count of 1

Add a pipeline configuration option to exempt the names corpus from the multi-source requirement and minimum count threshold. Names should pass through to romanization with only basic validation (is valid Thai text, is not a single character, is not already in the vocabulary from text corpora).

Names that DO appear in text corpora (e.g., common names like สมชาย that appear in news articles) should have their text-corpus frequency preserved — the names corpus adds them to the vocabulary if they're missing, but doesn't override existing frequency data.

### Phase 2: Frequency Normalization

**Task 2.1 — Corpus weight configuration:**

Add a configurable weight for the names corpus in the frequency normalization step. The current pipeline normalizes frequencies across corpora using equal-weight averaging. The names corpus needs its own weight parameter:

```yaml
# pipeline config (example)
corpus_weights:
  thwiki: 1.0
  prachathai: 1.0
  wisesight: 1.0
  wongnai: 1.0
  names: 0.3  # tunable — lower weight so names don't compete with common words
```

The weight controls how much "presence" a name gets in the combined frequency. With uniform count=1 and weight=0.3, a name will have lower frequency than any word that appears even moderately in text corpora, but higher frequency than the absolute floor. This is the desired behavior: names should appear in candidates when the user types a romanized name, but shouldn't outrank common vocabulary for ambiguous inputs.

**Task 2.2 — Frequency assignment for names:**

Since all names have uniform count=1, their normalized frequency within the names corpus is `1/N` where N is the total number of names. After applying the corpus weight, their contribution to the combined frequency will be small but nonzero. This means:

- Names will appear in the trie and be findable by prefix search
- Names will rank below common vocabulary for the same romanization key (e.g., if "mai" matches both ไม่ (common word) and a name ไม้, the common word ranks higher)
- Names will rank above the frequency floor, so they appear as valid candidates

### Phase 3: Romanization Generation

**Task 3.1 — Run names through the standard romanization pipeline:**

Process all names through TLTK `th2roman()` + the variant generator, same as regular vocabulary. This produces Thai-pronunciation-based romanizations.

Known challenges for names:
- TLTK's syllable decomposition may fail on unusual name spellings (names often use rare character combinations)
- Some names contain characters or clusters that the component dictionary (R003) doesn't cover
- Multi-syllable names may produce excessive variant explosion via Cartesian product

Mitigation: set `max_variants_per_word` lower for names (e.g., 10 instead of 20) to limit trie size growth. Names that fail TLTK decomposition entirely should be logged and added to a manual romanization file for the maintainer to handle.

**Task 3.2 — TLTK failure handling:**

Names that produce empty or clearly wrong TLTK output should be:
1. Logged to a failures file (`data/names/romanization-failures.txt`)
2. Excluded from the trie dataset (rather than included with bad romanization)
3. Manually romanized by the maintainer if they're common/important names
4. Added via the overrides mechanism (same pattern as CP07)

### Phase 4: Permissioned Source Integration (conditional)

If the maintainer receives permission from behindthename.com and/or thai-language.com:

**Task 4.1 — Data extraction:**
- behindthename.com: scrape paginated name listings (Thai name + romanization pairs) or use the dataset if provided directly by the owner
- thai-language.com: extract name tables from the three identified pages

**Task 4.2 — Integration with existing pipeline:**
- Names from permissioned sources are added to the `names/processed/` directory with source attribution
- Names that come with pre-existing romanizations (behindthename, thai-language.com) get those romanizations added as additional trie keys alongside the TLTK-generated ones, with higher confidence (0.9) since they are human-curated
- Deduplicate against Phase 1 names — if a name appears in both thai-names-corpus and behindthename, keep all romanization variants from both sources

**Task 4.3 — License compliance:**
- Document the license terms for each source in `data/names/README.md`
- Verify license compatibility with THAIME's MPL-2.0
- Add required attribution notices

### Phase 5: Validation

Validation is qualitative — the maintainer tests name inputs in the CLI/TUI:

- Type 20–30 common Thai first names by romanization and verify candidates appear
- Type 10–15 common Thai surnames and verify candidates appear
- Type 5–10 Thai nicknames (if nickname data is available) and verify candidates appear
- Check that name additions don't degrade existing word candidate quality (names shouldn't outrank common words for ambiguous inputs)
- Verify the total trie size increase is acceptable (expected: a few thousand additional entries, adding ~10-20% to trie key count)

## Limitations

- **No frequency data for names.** All names receive uniform frequency, so the engine cannot distinguish common names (สมชาย) from rare ones (สิริกัญญาพร). This means name candidates are ranked purely by romanization match quality and unigram cost floor, not by popularity. Acquiring name frequency data (e.g., from census statistics) would improve ranking but is not available publicly.

- **Romanization is only phonologically generated.** The pipeline produces romanizations based on Thai phonological rules (via TLTK + variant generator), not based on how real people actually romanize their names. A person named ณัฐ who romanizes as "Nutch" will not find their name unless they also try "nat" (the phonologically predicted form). User dictionary remains the answer for personal romanization preferences.

- **TLTK decomposition failures on names.** Names frequently contain unusual character combinations that TLTK's syllable decomposition doesn't handle well (this was noted in R003 as affecting ~5% of syllables). The failure rate for names may be higher than for common vocabulary. Failed names are excluded rather than included with bad romanizations.

- **Phase 2 sources may not materialize.** Permission from behindthename.com and thai-language.com is not guaranteed. The plan is designed so Phase 1 alone delivers value — Phase 2 is additive, not required.

- **Name/word ambiguity.** Some Thai words are also names (e.g., มานะ is both the name "Mana" and the word "perseverance"). The pipeline doesn't need to distinguish these — the same Thai text appears once in the trie regardless of whether it's a name, a word, or both. Frequency from text corpora (if available) takes precedence over the uniform name frequency.

## Task Summary

| Phase | Task | Description | Effort | Blocking on |
|-------|------|-------------|--------|-------------|
| 1 | T1.1 | Corpus directory structure | 0.5 day | — |
| 1 | T1.2 | Name ingestion script | 0.5 day | — |
| 1 | T1.3 | Pipeline filter adjustments | 1 day | T1.1, T1.2 |
| 2 | T2.1 | Corpus weight configuration | 0.5 day | T1.3 |
| 2 | T2.2 | Frequency assignment design | 0.5 day | T2.1 |
| 3 | T3.1 | Romanization generation for names | 1 day | T1.2 |
| 3 | T3.2 | TLTK failure handling | 0.5 day | T3.1 |
| 4 | T4.1 | Permissioned source extraction | 1–2 days | Permission granted |
| 4 | T4.2 | Pipeline integration for Phase 2 sources | 1 day | T4.1 |
| 4 | T4.3 | License compliance documentation | 0.5 day | T4.1 |
| 5 | T5 | Validation (qualitative, maintainer-led) | 1 day | T3.1 |

**Phase 1–3 effort:** ~4.5 days
**Phase 4 effort:** ~2.5–3.5 days (conditional on permission)
**Phase 5 effort:** ~1 day

## Open Questions

1. **What corpus weight should names get?** The initial value of 0.3 is a guess. Too high and names compete with common words on ambiguous inputs; too low and names are effectively invisible. The TUI's live parameter tuning could help find the right value, but the weight applies at pipeline time (not engine runtime), so iteration requires rebuilding the trie.

2. **Should the names corpus participate in n-gram counting?** Names don't appear in sentence contexts in the names corpus (they're just lists), so they contribute nothing to bigram/trigram data. However, names DO appear in text corpora (news articles mention people). The current n-gram pipeline already captures these. No action needed — just noting that the names corpus is excluded from n-gram counting by design.

3. **How to handle foreign names in Thai script?** The thai-language.com foreign names page (http://www.thai-language.com/id/589838) contains foreign names transliterated into Thai (e.g., จอห์น for "John"). These could be useful — a user typing "john" might want จอห์น. But this overlaps with the loanword approach (CP09). Consider handling foreign-name-in-Thai as a loanword subcase rather than duplicating in the names corpus.

4. **Should nicknames be treated differently?** Thai nicknames (ชื่อเล่น) are often single syllables (บี, เอ, โอ, นิว) that collide heavily with common Thai words and particles. Including them may add noise. Consider either excluding nicknames from Phase 1 or giving them even lower weight than full names.

5. **What about romanized Thai name conventions?** Some Thai names follow specific romanization conventions set by the Royal Institute for passports. If this data becomes available, it could serve as a high-confidence romanization source. Currently not accessible.

## References

- Research 001: Romanization Source Audit — `research/001-romanization-source-audit/summary.md`
- Research 003: Component Romanization — `research/003-component-romanization/summary.md`
- Change Plan 05: Trie Pipeline — `docs/plans/change-plan-05-trie-pipeline.md`
- Change Plan 07: Trie Quality — `docs/plans/change-plan-07-trie-quality.md`
- thai-names-corpus: https://github.com/korkeatw/thai-names-corpus (CC-BY 4.0)
- Behind the Name (Thai): https://www.behindthename.com/submit/names/usage/thai
- thai-language.com names: http://www.thai-language.com/id/589844
- thai-language.com nicknames: http://www.thai-language.com/id/589843
- thai-language.com foreign names: http://www.thai-language.com/id/589838
