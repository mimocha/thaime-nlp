# Thai Romanization Source Audit: Background Research & Hypothesis

**Topic:** research/001-romanization-source-audit
**Date:** 2026-03-04
**Author:** Claude (agent)

## Problem Statement

THAIME's core data structure is a trie mapping Latin (romanized) character sequences to Thai words. The quality and coverage of this trie depends entirely on the romanization sources used to populate it. No single canonical source exists for Latin-to-Thai mappings — we need to audit all viable sources, evaluate what each produces, and determine which are practically usable for trie construction.

Key sub-questions:
1. What romanization sources exist for Thai?
2. What does each source produce, and is it programmatically accessible?
3. How do sources compare on a common word set?
4. Which source(s) best approximate informal Thai romanization (the "karaoke test")?

## Background Research

### Thai Romanization Systems

Multiple romanization systems exist for Thai, each designed for different purposes:

| System | Type | Tones | Vowel Length | Reversible | Use Case |
|--------|------|-------|-------------|-----------|----------|
| RTGS | Transcription | No | No | No | Official government use, road signs |
| ISO 11940 | Transliteration | Yes (diacritics) | Yes | Yes | Library cataloguing, academic |
| ISO 11940-2 | Transcription | No | No | No | Nearly identical to RTGS |
| Paiboon+ | Transcription | Yes | Yes | No | Language textbooks, learners |
| IPA | Phonetic | Yes | Yes | N/A | Linguistics, academic |

**RTGS** is the de facto standard but loses tonal and vowel-length information, making it a lossy many-to-one mapping. **ISO 11940** is fully reversible but uses diacritics that don't match how anyone actually types. Neither matches informal romanization patterns.

**Informal Thai romanization** ("ภาษาคาราโอเกะ") has no standard — Thai speakers romanize idiosyncratically. Common patterns include: tones ignored, vowel length ignored, silent letters dropped, English-influenced consonant mapping, and letter elongation for emphasis ("khaaa", "krubbb"). This is the target behavior THAIME must support.

### Source 1: PyThaiNLP Romanization Engines

PyThaiNLP v5.2.0 provides 5 romanization engines via `romanize()`:

| Engine | Method | Quality | Notes |
|--------|--------|---------|-------|
| `royin` (default) | Rule-based | Poor | Official RTGS rules but buggy output (e.g., สวัสดี → "satti") |
| `thai2rom` | Seq2Seq deep learning | Best overall | Requires PyTorch; downloads model on first use |
| `thai2rom_onnx` | Same model, ONNX runtime | Same as thai2rom | Faster inference |
| `tltk` | Rule-based via TLTK | Best rule-based | e.g., สวัสดี → "sawatdi" |
| `lookup` | Dictionary lookup | Variable | Uses human-curated Thai-English Transliteration Dictionary v1.4; falls back to another engine for unknown words |

Additional relevant PyThaiNLP features:
- **`transliterate(engine="iso_11940")`** — Pure character-level ISO 11940 mapping (reversible)
- **`soundex(engine="prayut_and_somchaip")`** — Cross-language Thai-English soundex that can match Thai words with Latin romanizations
- **`word_approximation()`** — Phonetic distance computation between words
- **`follow_rtgs()`** — Checks whether a word's transliteration follows RTGS

### Source 2: TLTK (Thai Language Toolkit)

TLTK v1.10 provides a full grapheme-to-phoneme pipeline:

| Function | Output | Notes |
|----------|--------|-------|
| `g2p()` | Internal phonemic notation with tones | Core engine; all others build on this |
| `th2roman()` | RTGS-like romanization | Best rule-based quality; strips tones and vowel length |
| `th2ipa()` | IPA with tone numbers | Full phonetic transcription |
| `th2ipa_all()` | All possible IPA readings | Exposes pronunciation ambiguity |
| `spell_variants()` | Alternative Thai spellings | Words with same pronunciation; useful for reverse mapping |

Key insight: TLTK's `th2ipa_all()` reveals that many Thai words have multiple valid pronunciations, which means the romanization problem is inherently many-to-many.

### Source 3: Pre-built Datasets

| Dataset | Size | License | Format | Notes |
|---------|------|---------|--------|-------|
| PyThaiNLP thai2rom-dataset | 648K pairs | CC0 (public domain) | CSV | Directly downloadable; mixed/learned romanizations |
| Wiktionary Thai entries | 16K+ entries | CC-BY-SA 3.0 | Structured (extractable via wiktextract) | RTGS, IPA, Paiboon systems |
| AyutthayaAlpha | 1.2M Thai name pairs | Check paper (2024) | Research dataset | Proper names only |
| TRANSLIT | 1.6M entries (180+ langs) | Research | GitHub | Not Thai-specific |

The **thai2rom-dataset** (CC0, 648K pairs) is the most immediately actionable bulk dataset.

### Source 4: Karaoke/Online Sources

| Source | Size | API | License | Notes |
|--------|------|-----|---------|-------|
| thai-language.com | 30K+ entries | No API | Proprietary | Custom phonemic system; 6 romanization systems available on-site |
| thai2english.com | 100K+ entries | No API | Proprietary | Includes tone markers and component breakdowns |
| thai2karaoke (GitHub) | Tool | Open source | Open source | Converts Thai to karaoke romanization |
| thpronun (TLWG) | Tool | CLI | Free software | C/C++ Thai pronunciation analyzer; multiple output systems |
| Longdo Dictionary | Large | HTML only | Mixed | Unclear romanization data; unofficial JSON wrappers exist |

### Source 5: Soundex/Phonetic Algorithms

PyThaiNLP provides 4 soundex engines:

| Engine | Cross-language | Notes |
|--------|---------------|-------|
| `udom83` | No (Thai only) | 7-character code |
| `lk82` | No (Thai only) | 4-character code |
| `metasound` | No (Thai only) | Metaphone + Soundex hybrid |
| `prayut_and_somchaip` | Yes (Thai + English) | Can match Thai words with Latin romanizations |

The `prayut_and_somchaip` engine is directly relevant — it can generate matching codes for Thai text and its Latin romanization. This could serve as a fuzziness mechanism for trie lookup.

### Relevance to THAIME

THAIME needs Latin-to-Thai mappings (the reverse of what most tools provide). The approach would be:
1. Generate Thai-to-Latin romanizations from multiple sources
2. Invert them to create Latin-to-Thai lookup entries
3. Assign confidence weights based on source reliability
4. Use phonetic algorithms (soundex) for fuzzy matching at runtime

No existing tool provides the reverse mapping (Latin → Thai) directly. THAIME must build this from the forward mappings.

## Hypothesis / Proposed Approach

Based on the background research, we hypothesize that:

1. **A multi-source approach is necessary.** No single source covers both formal and informal romanization patterns. We should combine:
   - TLTK `th2roman()` as the high-quality rule-based baseline (RTGS-like)
   - PyThaiNLP `thai2rom` for learned romanizations that may capture patterns beyond rules
   - The thai2rom-dataset (648K pairs) as bulk coverage
   - Wiktionary data for curated, multi-system romanizations

2. **The `royin` engine in PyThaiNLP has quality issues** and should not be relied upon. TLTK's implementation is significantly better for rule-based RTGS.

3. **Informal romanization is too variable to capture from any single source**, but we can approximate it through:
   - Generating multiple romanization variants per word (RTGS + learned + lookup)
   - Using soundex/phonetic algorithms to provide fuzzy matching
   - Potentially using TLTK's `spell_variants()` to expand coverage

4. **The thai2rom-dataset is the most promising bulk source** given its size (648K pairs), permissive license (CC0), and direct downloadability.

The experiment phase should: (a) generate romanizations from each programmatic source on a common word set, (b) compare outputs qualitatively and quantitatively, and (c) assess the thai2rom-dataset's coverage and quality.

## Sources

- PyThaiNLP documentation: https://pythainlp.github.io/
- PyThaiNLP thai2rom-dataset: https://github.com/wannaphong/thai-romanization (CC0)
- TLTK: https://pypi.org/project/tltk/
- RTGS: https://en.wikipedia.org/wiki/Royal_Thai_General_System_of_Transcription
- ISO 11940: https://en.wikipedia.org/wiki/ISO_11940
- Wiktionary Thai romanization: https://en.wiktionary.org/wiki/Wiktionary:Thai_romanization
- Wiktionary Thai terms with IPA: https://en.wiktionary.org/wiki/Category:Thai_terms_with_IPA_pronunciation
- wiktextract: https://github.com/tatuylonen/wiktextract
- AyutthayaAlpha (2024): https://arxiv.org/abs/2412.03877
- thai2karaoke: https://github.com/comdevx/thai2karaoke
- thpronun (TLWG): https://github.com/tlwg/thpronun
- thai-language.com: http://www.thai-language.com/dict
- Thai NLP resources collection: https://github.com/kobkrit/nlp_thai_resources
