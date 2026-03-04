# Thai Romanization Source Audit & Feasibility

**Date:** 2026-03-04
**Author:** Claude (agent)
**Branch:** `research/001-romanization-source-audit`
**Status:** Complete

## Research Question

What romanization sources exist for generating Latin-to-Thai word mappings, what does each produce, and which are practically usable for constructing THAIME's lookup trie?

## Approach

We audited all viable programmatic sources for Thai romanization by running 6 engines on a curated set of 80 Thai words spanning 7 categories (common, food, places, verbs, slang, compounds, loanwords). We evaluated each source on output quality, coverage, accessibility, licensing, and failure modes. We also assessed the cross-language soundex algorithm as a fuzzy matching mechanism, analyzed the 648K-entry thai2rom-dataset for bulk coverage, tested TLTK's advanced phonemic features, built and tested thpronun (TLWG's C++ pronunciation analyzer), analyzed thai2karaoke (a JavaScript neural-network tool), and evaluated three web-based romanization sources (thai-language.com, thai2english.com, and Wiktionary).

## Key Findings

- **TLTK `th2roman()` is the best rule-based romanization engine.** It produced correct output for 79/80 test words (98.75%) and closely matched expected informal romanizations. It should be the primary romanization source for THAIME's trie.

- **PyThaiNLP's `royin` engine has critical quality issues.** It produced severely degraded romanizations for many common words (e.g., สวัสดี → "satti", ครับ → "khnap", อยุธยา → "uta", ส้มตำ → "smtam"). It should not be used as a romanization source.

- **PyThaiNLP's `lookup` engine is uniquely valuable for loanwords.** It returns the English source word for loanwords (e.g., แท็กซี่ → "taxi", อินเทอร์เน็ต → "internet", เฟซบุ๊ก → "facebook"), which matches how users would actually type these words. It falls back to the buggy `royin` engine for non-loanwords, so it should only be used selectively for its loanword mappings.

- **The `thai2rom` deep learning engine could not be tested** (requires PyTorch, which was not installed). Based on documentation and the thai2rom-dataset it was trained on, it likely produces RTGS-like output similar to TLTK. Testing this engine is a follow-up task.

- **Cross-language soundex is not viable.** The `prayut_and_somchaip` implementation achieved only a 5% match rate between Thai text and its Latin romanization — essentially random. The algorithm maps characters to phonetic groups differently across scripts, making cross-script matching fundamentally broken. This approach should be abandoned.

- **The thai2rom-dataset (648K pairs, CC0) is large but shallow.** Every entry is a 1:1 mapping (one romanization per word) and the romanizations are RTGS-style. It provides broad vocabulary coverage (96.3% overlap with our 80-word test set) but no variant romanizations. Missing words are slang and recent loanwords.

- **45% of Thai words have multiple possible pronunciations** (per TLTK's `th2ipa_all()`), confirming that romanization is inherently a many-to-many problem. However, TLTK's advanced features (`th2ipa_all`, `spell_variants`) have stability issues and crash on many inputs.

- **No tested source produces informal romanization patterns.** The vowel-doubling convention common in informal Thai romanization (e.g., "sawatdee" vs RTGS "sawatdi", "moo" vs "mu", "dee" vs "di") is absent from all programmatic sources. This is the biggest gap — THAIME will need a rule-based variant generator to produce informal forms from RTGS-like base romanizations.

- **thpronun (TLWG) is a strong secondary source with unique multi-reading capability.** Built from source and tested on all 80 words with 0 errors. It produces an average of 3.4 pronunciation readings per word (45% of words have multiple readings), with the correct reading usually present among the alternatives. Its syllable-aligned JSON output (e.g., สวัสดี → ["sa","wat","di"]) is directly useful for trie construction. Best-reading match rate with informal romanization: 61.3% exact, 70.0% after normalization. GPL-3.0 licensed — the tool can't be embedded in THAIME, but its output data is usable.

- **Wiktionary is the most promising unexploited data source.** It uniquely provides three romanization systems (RTGS, IPA, Paiboon) for 16K+ Thai entries in structured, extractable form under CC-BY-SA 3.0. The Paiboon system — used in language textbooks — may be the closest available approximation to informal romanization from any structured source. Pre-extracted data is available via the wiktextract tool.

- **thai2karaoke (comdevx) is not useful.** The JavaScript neural-network tool classifies Thai syllables into vowel groups using ~600 training patterns, but is unmaintained (last update 2019), requires pre-segmented input, and provides no advantage over TLTK's rule-based approach.

- **Proprietary web sources are high quality but not extractable.** thai-language.com (30K+ entries) and thai2english.com (100K+ entries) both have excellent romanization with tone information, but are proprietary with no APIs. Useful as manual validation references only.

## Recommendation

For THAIME's trie construction, adopt a **layered multi-source strategy**:

1. **Primary source: TLTK `th2roman()`** — Use as the high-confidence base romanization for every Thai word. Assign highest source weight.

2. **Loanword supplement: PyThaiNLP `lookup` engine** — Extract loanword mappings only (where lookup returns a recognizable English word, not a `royin` fallback). These get high source weight for the specific words they cover.

3. **Bulk coverage: thai2rom-dataset** — Use the 648K-entry CC0 dataset for vocabulary breadth. Assign moderate source weight (output is RTGS-like and largely redundant with TLTK).

4. **Multi-reading expansion: thpronun** — Use thpronun's syllable-aligned JSON output to generate alternative romanization forms for words with ambiguous pronunciation. Its multiple readings per word provide natural trie expansion. Note: requires building from source (C++); cannot be embedded due to GPL-3.0, but generated romanization data can be included.

5. **Informal variant generation (new work needed):** Build a rule-based expander that takes RTGS-like romanizations and generates informal variants:
   - Vowel doubling: i → ee, u → oo, a → aa (for long vowels)
   - Final consonant softening: t → d, p → b
   - Common informal spellings: kh → k, th → t (simplified consonant clusters)
   - This is the highest-impact future research task identified by this audit.

5. **Do NOT use:** PyThaiNLP `royin` engine (buggy), cross-language soundex (non-functional), ISO 11940 transliteration (uses diacritics, not how people type), thai2karaoke (unmaintained, no advantage over TLTK).

6. **Future investigation:** Test the `thai2rom` deep learning engine with PyTorch installed. **Extract Wiktionary Thai data via wiktextract** — this is the highest-value unexplored data source, providing multi-system romanization (RTGS + IPA + Paiboon) under CC-BY-SA 3.0. The Paiboon romanization system is the closest to informal Thai romanization available from any structured source and could reduce the need for rule-based variant generation. Also investigate CC-BY-SA 3.0 compatibility with THAIME's MPL 2.0 license.

## Limitations

- The `thai2rom` Seq2Seq engine was not tested due to missing PyTorch dependency. This is the most likely source of higher-quality learned romanizations.
- The 80-word test set, while spanning 7 categories, is small. A broader evaluation against the full thai2rom-dataset would strengthen conclusions.
- Wiktionary data was evaluated structurally but not extracted and tested with live data — this is a recommended follow-up.
- Informal romanization quality was assessed subjectively. A formal evaluation would require a ground-truth dataset of informal romanizations from Thai speakers.
- TLTK's `th2ipa_all()` and `spell_variants()` crashed on many inputs, so the 45% ambiguity figure is a lower bound.
- thpronun was tested without its exception dictionary (build issue), causing more spurious readings than expected. With the exception dictionary, reading counts would be lower and more accurate.

## References

- Experiment branch: `research/001-romanization-source-audit`
- Experiment artifacts: `experiments/001-romanization-source-audit/`
- PyThaiNLP documentation: https://pythainlp.github.io/
- PyThaiNLP thai2rom-dataset: https://github.com/wannaphong/thai-romanization (CC0)
- TLTK: https://pypi.org/project/tltk/
- RTGS: https://en.wikipedia.org/wiki/Royal_Thai_General_System_of_Transcription
- Wiktionary Thai romanization: https://en.wiktionary.org/wiki/Wiktionary:Thai_romanization
- thpronun (TLWG): https://github.com/tlwg/thpronun (GPL-3.0)
- thai2karaoke: https://github.com/comdevx/thai2karaoke
- thai-language.com: http://www.thai-language.com/
- thai2english.com: https://www.thai2english.com/
- Wiktionary Thai entries: https://en.wiktionary.org/wiki/Category:Thai_terms_with_IPA_pronunciation
- wiktextract: https://github.com/tatuylonen/wiktextract
