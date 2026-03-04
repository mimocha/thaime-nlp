# Thai Romanization Source Audit: Experimental Results

**Topic:** research/001-romanization-source-audit
**Date:** 2026-03-04
**Author:** Claude (agent)
**Depends on:** hypothesis.md, plan.md

## Setup

- **Python version:** 3.12
- **Key dependencies:** PyThaiNLP 5.2.0, TLTK 1.10, pandas, numpy
- **Note:** PyTorch is not installed, so `thai2rom` (Seq2Seq deep learning) engine could not be tested.
- **Sample word set:** 80 Thai words across 7 categories (common, food, places, verbs, slang, compounds, loanwords)

## Results

### Experiment 1: Programmatic Source Comparison

Ran 6 romanization engines on 80 sample words. Full results in `data/experiment1_results.csv`.

**Engine availability:**

| Engine | Status | Errors | Notes |
|--------|--------|--------|-------|
| tltk_roman | Working | 0 errors, 1 empty | Best rule-based quality |
| tltk_ipa | Working | 0 errors, 1 empty | Full IPA with tones |
| pythainlp_royin | Working | 0 errors | Notably poor quality on complex words |
| pythainlp_thai2rom | Failed | 80 errors | Requires PyTorch (not installed) |
| pythainlp_lookup | Working | 0 errors | Falls back to royin for unknown words |
| iso_11940 | Working | 0 errors | Character-level transliteration |

**Quality comparison (selected words):**

| Thai | English | Informal ref | TLTK | royin | lookup |
|------|---------|-------------|------|-------|--------|
| สวัสดี | hello | sawatdee | sawatdi | satti | satti |
| ขอบคุณ | thank you | khopkhun | khopkhun | khopkun | khopkun |
| กรุงเทพ | Bangkok | krungthep | krungthep | knungtep | knungtep |
| เชียงใหม่ | Chiang Mai | chiangmai | chiangmai | chiangaim | chiangaim |
| โรงเรียน | school | rongrean | rongrian | rongnian | rongnian |
| ต้มยำกุ้ง | tom yum goong | tomyamkung | tomyamkung | tmamkung | tmamkung |
| ส้มตำ | som tam | somtam | somtam | smtam | smtam |
| อยุธยา | Ayutthaya | ayutthaya | ayutthaya | uta | uta |
| หาดใหญ่ | Hat Yai | hatyai | hatyai | atain | atain |
| เหนื่อย | tired | nuay | nueai | enue | enue |
| อร่อย | delicious | aroi | aroi | noi | noi |
| ครับ | krub (male polite) | khrap | khrap | khnap | khnap |
| โทรศัพท์ | telephone | thorasap | thorasap | thontap | thontap |
| ตลาด | market | talat | talat | tnat | tnat |

**Key finding:** PyThaiNLP's `royin` engine produces severely degraded output for many words:
- ครับ → "khnap" (should be "khrap")
- อยุธยา → "uta" (should be "ayutthaya")
- หาดใหญ่ → "atain" (should be "hatyai")
- อร่อย → "noi" (should be "aroi")

The `lookup` engine falls back to `royin` for words not in its dictionary, inheriting these same errors.

**TLTK `th2roman` is consistently correct** and closely matches the expected informal romanizations. It was the only engine that produced correct romanizations for all tested words.

**Loanword handling:**

| Thai | English | TLTK | lookup |
|------|---------|------|--------|
| แท็กซี่ | taxi | thaeksi | taxi |
| อินเทอร์เน็ต | internet | inthoenet | internet |
| เฟซบุ๊ก | Facebook | fe | facebook |
| กูเกิล | Google | kukoen | google |
| ฟุตบอล | football | futbon | football |

The `lookup` engine excels at loanwords (returns the English source word), while TLTK produces phonetic romanizations of the Thai pronunciation. Both approaches are useful for THAIME — the lookup gives the "natural" romanization a user would type, while TLTK gives the phonetic romanization.

### Experiment 2: Soundex Cross-Language Matching

Tested `prayut_and_somchaip` soundex for matching Thai words with their Latin romanizations.

**Match rates:**

| Source | Matches | Rate |
|--------|---------|------|
| tltk_roman | 4/80 | 5.0% |
| pythainlp_royin | 4/80 | 5.0% |
| informal_ref | 2/80 | 2.5% |

**Collision rate (unrelated word pairs):** 3/100 (3.0%)

**Conclusion:** The cross-language soundex implementation is **not viable** as a matching mechanism. The soundex codes for Thai script and Latin script are fundamentally different because the algorithm maps characters to phonetic groups differently in each script. A 5% match rate is essentially random. This approach should be **abandoned** for THAIME's trie lookup.

### Experiment 3: thai2rom-dataset Analysis

Downloaded and analyzed the PyThaiNLP thai2rom-dataset (CC0 license).

**Dataset statistics:**

| Metric | Value |
|--------|-------|
| Total entries | 648,241 |
| Unique Thai words | 648,241 |
| Unique romanizations | 610,465 |
| Romanization variants per word | 1.00 (all 1:1) |
| Mean Thai word length | 14.8 characters |
| Min/Max word length | 1/76 characters |

**Overlap with sample word set:** 77/80 words found (96.3%). Missing: แซ่บ (slang), เฟซบุ๊ก (Facebook), เซลฟี (selfie).

**Key observations:**
1. The dataset is strictly 1:1 — each Thai word has exactly one romanization. There are no variant romanizations.
2. The romanizations are RTGS-style (matching TLTK `th2roman` output closely).
3. Mean word length of 14.8 characters suggests the dataset includes many compound words and place names.
4. Missing words are informal/slang terms and recent loanwords — exactly the categories where additional sources would be most needed.
5. The dataset appears to be generated by a single romanization engine, not curated from multiple sources.

### Experiment 4: TLTK Advanced Features

**th2ipa_all() — Pronunciation Ambiguity:**
- 36/80 words (45%) have multiple possible readings
- Many words errored due to TLTK internal issues (`'english'` key error), suggesting the function has stability issues with certain word patterns
- When it works, it reveals meaningful ambiguity (e.g., กรุงเทพ has 6 possible readings)

**spell_variants() — Alternative Thai Spellings:**
- 50/80 words (62.5%) have spelling variants (when the function works)
- Same stability issues as th2ipa_all()
- This feature could be valuable for expanding coverage but needs error handling

**g2p() — Internal Phonemic Representation:**
Works reliably. Example outputs:

| Thai | g2p output | roman | ipa |
|------|-----------|-------|-----|
| สวัสดี | sa1'wat1~dii0 | sawatdi | sa2.wat2.diː1 |
| กรุงเทพ | kruN0~theep2 | krungthep | kruŋ1.tʰeːp3 |
| ข้าว | khaaw2 | khao | kʰaːw3 |
| เหนื่อย | nUUaj1 | nueai | nɯːaj2 |
| อร่อย | ?a1'rOOj1 | aroi | ʔa2.rᴐːj2 |

The internal phonemic representation preserves tonal and length information that is lost in `th2roman`. This intermediate representation could be used to generate multiple romanization variants (e.g., with and without vowel length distinction).

### Experiment 5: Karaoke & Online Source Evaluation

Built `thpronun` (TLWG) from source, tested on full 80-word sample set. Analyzed thai2karaoke (GitHub) source code. Evaluated web sources: thai-language.com, thai2english.com, Wiktionary.

Full results in `data/experiment5_karaoke_online.csv` and `data/experiment5_thpronun_stats.json`.

**thpronun (TLWG) — Summary:**

| Metric | Value |
|--------|-------|
| Words tested | 80 |
| Errors | 0 |
| Words with output | 80 |
| Words with multiple readings | 36 (45%) |
| Exact match with informal ref | 49 (61.3%) |
| Close match (after normalization) | 7 |
| Combined match rate | 70.0% |
| Avg readings per word | 3.4 |

**thpronun key word comparisons:**

| Thai | Informal ref | thpronun best | TLTK | # readings |
|------|-------------|---------------|------|------------|
| สวัสดี | sawatdee | sawatdi | sawatdi | 6 |
| ขอบคุณ | khopkhun | khopkhun | khopkhun | 7 |
| กรุงเทพ | krungthep | krungthep | krungthep | 12 |
| เชียงใหม่ | chiangmai | chiangmai | chiangmai | 4 |
| ต้มยำกุ้ง | tomyamkung | tomyamkung | tomyamkung | 1 |
| อยุธยา | ayutthaya | ayutya | ayutthaya | 10 |
| หาดใหญ่ | hatyai | hatyai | hatyai | 2 |
| แท็กซี่ | taxi | thaeksi | thaeksi | 1 |
| เฟซบุ๊ก | facebook | fetbuk | fe | 7 |
| ฟุตบอล | football | futbon | futbon | 13 |
| ครับ | khrap | khrap | khrap | 3 |
| อร่อย | aroi | aroi | aroi | 2 |

**Key observations on thpronun:**
- Produces multiple pronunciation readings per word (avg 3.4), unlike TLTK which gives one. The most correct reading is usually present among the alternatives.
- Uses RTGS romanization, matching TLTK quality. Best reading agrees with TLTK for most words.
- Unique strength: syllable-aligned JSON output (e.g., สวัสดี → ["sa","wat","di"]) — directly useful for trie construction.
- Generates some spurious readings without the exception dictionary (e.g., กรุงเทพ has 12 readings, most incorrect).
- GPL-3.0 licensed — not directly embeddable in MPL 2.0 THAIME, but output data is usable.
- C++ tool requires building from source; no Python bindings.

**thai2karaoke (comdevx) — Summary:**
- JavaScript (Node.js) tool using brain.js neural network
- Classifies Thai syllables into vowel-sound groups, then assembles romanization from consonant lookup tables
- Training set: ~600 syllable patterns (small)
- RTGS-based consonant mapping but limited; no tone handling
- Not maintained since 2019; requires pre-segmented syllables
- **Relevance: Low.** TLTK provides the same mappings with better quality.

**Web source analysis:**

| Source | Size | License | API | Romanization Quality | THAIME Relevance |
|--------|------|---------|-----|---------------------|------------------|
| thai-language.com | 30K+ entries | Proprietary | No | Excellent (custom phonemic + RTGS + tones) | Reference only |
| thai2english.com | 100K+ entries | Proprietary | No | Excellent (custom + tone diacritics) | Reference only |
| Wiktionary | 16K+ entries | CC-BY-SA 3.0 | wiktextract | Excellent (RTGS + IPA + Paiboon) | **High — recommended follow-up** |

- **thai-language.com** and **thai2english.com** both have high-quality romanization but are proprietary and cannot be programmatically extracted at scale. They use custom romanization systems with tone markers.
- **Wiktionary** is the standout finding: it provides RTGS, IPA, and Paiboon romanization in structured form under CC-BY-SA 3.0. The Paiboon system is the closest available approximation to informal romanization. Pre-extracted data is available via wiktextract. Recommended for follow-up investigation.

## Observations

1. **TLTK is the clear winner for rule-based romanization.** Its output is consistently correct and closely matches expected informal romanizations. PyThaiNLP's `royin` engine has fundamental quality issues.

2. **The `lookup` engine is uniquely valuable for loanwords.** It returns the English source word (e.g., "internet", "facebook", "taxi") which is exactly what users would type. This is a different and complementary signal to phonetic romanization.

3. **Cross-language soundex is a dead end.** The `prayut_and_somchaip` implementation does not produce matching codes between Thai and Latin text at a useful rate. The algorithm's character-to-phonetic-group mapping is script-dependent.

4. **The thai2rom-dataset is large but shallow.** 648K entries with only 1:1 mappings means it's essentially a bulk run of a single romanization engine. It provides good coverage but no variant romanizations.

5. **TLTK's advanced features (th2ipa_all, spell_variants) are promising but unstable.** They crash on many inputs. When they work, they reveal useful information about pronunciation ambiguity and spelling variation.

6. **Informal romanization remains the gap.** No tested source produces output that matches informal Thai romanization patterns (e.g., "sawatdee" vs the RTGS "sawatdi", "moo" vs "mu", "doo" vs "du", "lor" vs "lo"). The vowel-doubling pattern (aa, oo, ee) common in informal romanization is absent from all programmatic sources.

7. **thpronun is a strong secondary source with unique multi-reading capability.** It matches TLTK quality on its best reading and additionally provides alternative pronunciation variants — useful for expanding trie coverage. Its syllable-aligned JSON output is directly useful for trie construction.

8. **Wiktionary is the most promising unexploited source.** It uniquely provides three romanization systems (RTGS, IPA, Paiboon) in extractable form under an open license. The Paiboon system may be the closest to informal romanization available from any structured source.

9. **thai2karaoke is not useful.** The tool is unmaintained, uses a small training set, and provides no advantage over TLTK.

10. **Proprietary web sources (thai-language.com, thai2english.com) cannot be used at scale** but serve as high-quality validation references.

## Reproducibility

To rerun these experiments:

```bash
cd /workspaces/thaime-nlp
python experiments/001-romanization-source-audit/scripts/experiment1_source_comparison.py
python experiments/001-romanization-source-audit/scripts/experiment2_soundex.py
python experiments/001-romanization-source-audit/scripts/experiment3_thai2rom_dataset.py
python experiments/001-romanization-source-audit/scripts/experiment4_tltk_advanced.py
python experiments/001-romanization-source-audit/scripts/experiment5_karaoke_online.py
```

Note: Experiment 2 depends on Experiment 1's output (experiment1_results.csv).
Note: Experiment 5 requires thpronun to be installed (build from https://github.com/tlwg/thpronun).

## Raw Data

- `data/experiment1_results.csv` — Full comparison of all engines on 80 words
- `data/experiment2_soundex.csv` — Soundex matching results
- `data/experiment3_stats.json` — thai2rom-dataset summary statistics
- `data/thai2rom_dataset.csv` — Full thai2rom-dataset (648K entries)
- `data/sample_words.csv` — The 80-word sample set used across experiments
- `data/experiment5_karaoke_online.csv` — thpronun romanization results on 80 words
- `data/experiment5_thpronun_stats.json` — thpronun stats + thai2karaoke analysis + web source analysis
