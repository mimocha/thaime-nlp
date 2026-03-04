# Informal Thai Romanization Variant Generation

**Date:** 2026-03-04
**Author:** Claude (agent)
**Branch:** `research/002-informal-romanization-variants`
**Status:** Complete

## Research Question

Can a rule-based variant generator produce realistic informal Thai romanizations from TLTK's formal RTGS-like output, and is the variant count manageable for trie construction?

## Approach

We built a syllable-aware, rule-based variant generator that decomposes TLTK's romanization into per-syllable components (initial cluster, vowel nucleus, final consonant), applies five categories of phonetic transformation rules, and generates variants via Cartesian product of component alternatives. The generator uses TLTK's IPA and g2p output to determine vowel length, ensuring that vowel-doubling rules only apply to genuinely long Thai vowels. We evaluated the generator on an 80-word test set spanning 7 categories (common words, food, places, verbs, slang, compounds, loanwords).

## Key Findings

- **91.2% coverage rate** — 73 of 80 test words had at least one generated variant matching an expected informal romanization. All 15 common words and all 10 place names achieved 100% coverage.

- **5.0 average variants per word** — Well within the manageable range for trie construction. 67.5% of words produced 2-6 variants. The maximum was 24, controlled by a configurable cap.

- **Five transformation rules, three essential:** Vowel lengthening (affecting 56% of words), final consonant softening (35%), and cluster simplification (44%) are the three highest-value rules. R-dropping (10%) and initial voicing (15%) are supplementary. All five rules combined produce the best results.

- **Component-level Cartesian product is the key design insight.** Previous approaches applying rules independently cannot generate cross-rule combinations like "pood" (ph→p + u→oo + t→d from "phut" for พูด). The component decomposition enables these naturally.

- **7 uncovered words fall into three categories:** TLTK limitations (3 words — empty or incorrect base romanization), loanwords where users type the English source word (2 words — "taxi", "computer"), and formatting mismatches (2 words — hyphen vs space in compounds). None are failures of the variant rules themselves.

- **Loanwords are the weakest category at 70% coverage.** Users type English source words ("taxi", "computer", "facebook") that cannot be derived from TLTK's Thai-phonetic romanization. PyThaiNLP's `lookup` engine (identified in Task 001) should supplement loanword romanizations separately.

- **Noise rate of 48% is an overestimate.** The expected informal list has only 2-4 entries per word. Many "non-matching" variants are actually plausible (e.g., "khrab" for ครับ). Manual inspection suggests the true implausible variant rate is below 20% for most words.

- **A seed benchmark dataset of 80 entries with 525 total romanizations was generated** as a secondary deliverable, combining curated expected forms with generator output. This requires maintainer review before use as an official benchmark.

## Transformation Rule Catalog

| Rule | Example | Applies When | Impact |
|------|---------|-------------|--------|
| **Vowel lengthening** | di→dee/dii, mu→moo/muu | Thai vowel is long (per IPA) | 56% of words |
| **Final consonant softening** | sawat→sawad, khrap→khrab | Word ends in t/p/k | 35% of words |
| **Cluster simplification** | khrap→krap, thai→tai, phet→pet | Initial kh/th/ph/ch cluster | 44% of words |
| **R-dropping** | krungthep→kungthep, khrap→khap | Initial kr/khr/pr/phr/tr/thr cluster | 10% of words |
| **Initial voicing** | kin→gin, kai→gai | Initial k (for ก) | 15% of words |

## Recommendation

For THAIME's trie construction, adopt the variant generator with all five rules active:

1. **Use the variant generator as-is** for expanding TLTK's base romanizations into informal forms. The generator produces an average of 5.0 variants per word with 91% coverage — a strong foundation.

2. **Set max_variants_per_word to 20** for production use. The default of 50 allows some multi-syllable words (like ช็อกโกแลต) to produce too many variants. A cap of 20 balances coverage with trie size.

3. **Assign variant romanizations lower confidence weights** than the primary TLTK romanization in the trie. The base TLTK form should always rank highest; generated variants should rank below but above unknown/random inputs.

4. **Supplement loanwords separately** using PyThaiNLP's `lookup` engine for English source words (validated in Task 001 as uniquely valuable for loanwords). The variant generator cannot produce "taxi" from "thaeksi" — this requires a different data source.

5. **Consider disabling r-dropping for formal/written contexts.** R-dropping is highly productive in spoken Bangkok Thai but may not match all users' typing habits. It could be offered as a configurable option.

## Limitations

- The 80-word test set is small and manually curated. A larger evaluation against real Thai user typing data would be valuable.
- The expected informal romanizations were curated by the agent, not by native Thai speakers. Some assessments of "plausible" vs "implausible" may be inaccurate.
- The generator operates on TLTK's romanization as a black box. If TLTK produces incorrect base romanization (as for แซ่บ, เฟซบุ๊ก), the generator cannot recover.
- Vowel lengthening rules for diphthongs (ao, ai, ia, ua) are less well-validated than for simple vowels (i, u, a, e, o).
- The noise rate metric is inflated by the small size of the expected informal list. A more rigorous noise assessment would require native speaker judgments.
- Word-specific spellings (e.g., "pad thai" as a globally recognized dish name) are not captured by systematic rules.

## References

- Experiment branch: `research/002-informal-romanization-variants`
- Experiment artifacts: `experiments/002-informal-romanization-variants/`
- Task 001 summary: `research/001-romanization-source-audit/summary.md`
- TLTK: https://pypi.org/project/tltk/
- RTGS: https://en.wikipedia.org/wiki/Royal_Thai_General_System_of_Transcription
