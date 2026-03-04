# Thai Romanization Source Audit: Experimental Plan

**Topic:** research/001-romanization-source-audit
**Date:** 2026-03-04
**Author:** Claude (agent)
**Depends on:** hypothesis.md

## Experimental Variables

| Variable | Values | Description |
|----------|--------|-------------|
| Romanization source | `tltk.th2roman`, `pythainlp.romanize(royin)`, `pythainlp.romanize(thai2rom)`, `pythainlp.romanize(lookup)`, `pythainlp.transliterate(iso_11940)`, `tltk.th2ipa` | The tool/engine producing romanization |
| Word category | common, food, places, verbs, slang, compounds, loanwords | Category of Thai words tested |

## Evaluation Metrics

This is a qualitative survey, not a benchmark experiment. Evaluation is descriptive rather than numeric.

| Metric | Description | How Measured |
|--------|-------------|--------------|
| Coverage | Can the source romanize the word at all? | Binary pass/fail per word |
| Consistency | Does the source produce deterministic output? | Run each word 3x, check for variation |
| Informal similarity | How close is the output to informal Thai romanization? | Manual assessment on a 1-3 scale (1=formal/stiff, 2=acceptable, 3=natural) |
| Error rate | Does the source produce obviously wrong output? | Manual inspection |
| Uniqueness | How many unique romanizations does each source produce across all words? | Count distinct outputs per word across sources |

## Datasets

- **No benchmark used.** This is a pre-benchmark survey task.
- **Sample word set:** A curated list of ~80 Thai words spanning 7 categories (common, food, places, verbs, slang, compounds, loanwords). Stored in `experiments/001-romanization-source-audit/data/sample_words.csv`.
- **thai2rom-dataset:** Will download and analyze the 648K-pair CC0 dataset from PyThaiNLP for coverage/quality assessment.

## Procedure

### Experiment 1: Programmatic Source Comparison

1. Create a sample word set of ~80 Thai words across categories
2. Run each programmatic romanization source on every word
3. Collect outputs in a comparison table
4. Manually assess informal similarity scores
5. Document failures, errors, and notable differences

### Experiment 2: Soundex/Phonetic Algorithm Evaluation

1. For each word in the sample set, generate romanizations from all sources
2. Apply `prayut_and_somchaip` soundex to both the Thai word and each romanization
3. Check if the soundex codes match (cross-language matching capability)
4. Assess collision rates — do unrelated words produce matching codes?

### Experiment 3: thai2rom-dataset Analysis

1. Download the thai2rom-dataset (648K pairs)
2. Basic statistics: word count, unique Thai words, romanization variants per word
3. Sample 100 entries and manually assess quality
4. Check overlap with our sample word set
5. Assess licensing and usability for THAIME

### Experiment 4: TLTK Advanced Features

1. Test `th2ipa_all()` on the sample set to see how many ambiguous readings exist
2. Test `spell_variants()` to assess coverage of alternative spellings
3. Evaluate whether IPA as an intermediate representation could generate informal variants

### Experiment 5: Karaoke & Online Source Evaluation

1. Build and test `thpronun` (TLWG) — a C++ Thai pronunciation analyzer that outputs multiple romanization systems
2. Run thpronun on the full 80-word sample set; collect romanizations, syllable breakdowns, and reading counts
3. Analyze `thai2karaoke` (GitHub) — a JavaScript neural-network-based syllable classifier for karaoke romanization
4. Evaluate web-based sources: thai-language.com, thai2english.com, and Wiktionary Thai entries
5. For each source: document romanization system, API accessibility, licensing, and relevance to THAIME
6. Compare thpronun output against TLTK and informal romanization references

## Success Criteria

This is a survey task. Success means:
- All identified programmatic sources have been tested with concrete examples
- A clear comparison table exists showing each source's output on the same words
- Each source has a documented assessment of: quality, coverage, accessibility, licensing, and failure modes
- A ranked recommendation exists for which sources to pursue for trie construction
- At least one additional source beyond the three starting candidates has been investigated

## Dependencies

```
pythainlp>=5.0  # Already installed
tltk>=1.0       # Already installed
pandas           # Already installed
thpronun         # Built from source (C++, requires libthai-dev)
```

## Estimated Effort

- Experiment 1: ~30 minutes (scripted generation + manual review)
- Experiment 2: ~15 minutes (scripted)
- Experiment 3: ~20 minutes (download + analysis)
- Experiment 4: ~15 minutes (scripted)
- Experiment 5: ~45 minutes (thpronun build + testing + web source research)
- Results synthesis: ~30 minutes
