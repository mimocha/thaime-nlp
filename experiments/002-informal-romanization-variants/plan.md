# Informal Thai Romanization Variant Generation: Experimental Plan

**Topic:** research/002-informal-romanization-variants
**Date:** 2026-03-04
**Author:** Claude (agent)
**Depends on:** hypothesis.md

## Experimental Variables

| Variable | Values | Description |
|----------|--------|-------------|
| Transformation rules | 5 rules (individually toggleable) | Which phonetic transformation rules are active |
| Combination strategy | Component Cartesian product | How syllable-level transformations combine |
| Syllable awareness | TLTK g2p + IPA | Source of phonetic info for rule application |

### Transformation Rules

1. **Vowel lengthening** — Double short RTGS vowels for long Thai vowels (i→ee/ii, u→oo/uu, a→aa, e→ee, o→oo). Only applied when IPA/g2p confirms the vowel is long.
2. **Final consonant softening** — Voice final stops (t→d, p→b, k→g).
3. **Consonant cluster simplification** — Remove aspiration marker (kh→k, th→t, ph→p, ch→j/c). Also simplify three-char clusters (khr→kr, phr→pr, thr→tr).
4. **R-dropping** — Remove r from clusters (kr→k, khr→kh/k, pr→p, etc.).
5. **Initial voicing** — Voice unaspirated stops (k→g for ก).

## Evaluation Metrics

| Metric | Description | How Measured |
|--------|-------------|--------------|
| Coverage rate | % of test words where ≥1 generated variant matches an expected informal form | Count matches against curated expected list |
| Noise rate | Avg % of generated variants per word that are not in the expected list | (total_variants - matches) / total_variants |
| Expansion factor | Avg number of variants per word | total_variants / total_words |
| Max variants | Highest variant count for any single word | max(variants_per_word) |

## Datasets

- **Primary test set:** 80-word curated set spanning 7 categories (common, food, places, verbs, slang, compounds, loanwords), reconstructed from Task 001's methodology.
- **Expected informal romanizations:** 2-4 hand-curated plausible informal forms per word, used for coverage/noise assessment.
- **Phonetic data source:** TLTK's `th2roman()`, `th2ipa()`, `g2p()`, and `syl_segment()` output.

## Procedure

1. Run TLTK on all 80 test words to get base romanization, IPA, g2p, and syllable segmentation.
2. For each word, decompose into syllables and analyze each syllable's phonetic properties (vowel length, initial cluster, final consonant).
3. For each syllable, generate component variants (initial, vowel, final) based on active rules.
4. Combine component variants via Cartesian product within each syllable.
5. Combine syllable variants via Cartesian product across syllables.
6. Evaluate against expected informal romanizations.
7. Report coverage rate, noise rate, expansion factor, and per-category breakdown.

## Success Criteria

- **Coverage rate ≥ 80%** — The generator should produce at least one plausible informal variant for the large majority of test words.
- **Avg variants per word < 15** — The expansion factor should be manageable for trie construction.
- **Common words category coverage ≥ 90%** — The most frequently used words should have high coverage.

## Dependencies

```
pip install tltk pythainlp pandas numpy
```

## Estimated Effort

- Test set construction: ~30 minutes (reconstructing from Task 001 categories)
- Generator implementation: ~2 hours (syllable analysis + rule engine)
- Evaluation: ~30 minutes (automated evaluation + manual review)
- Documentation: ~1 hour (all research artifacts)
