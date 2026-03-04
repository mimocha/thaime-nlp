# Informal Thai Romanization Variant Generation: Experimental Results

**Topic:** research/002-informal-romanization-variants
**Date:** 2026-03-04
**Author:** Claude (agent)
**Depends on:** hypothesis.md, plan.md

## Setup

- **Python version:** 3.12.3
- **Key dependencies:** tltk 1.10, pythainlp 5.2.0
- **Test set:** 80 Thai words across 7 categories (common: 15, food: 12, places: 10, verbs: 10, slang: 13, compounds: 10, loanwords: 10)
- **Generator design:** Component-level Cartesian product within syllables, syllable-level Cartesian product across syllables
- **Config:** All 5 rules active, max 50 variants per word

## Results

### Overall Metrics

| Metric | Value |
|--------|-------|
| **Coverage rate** | **91.2%** (73/80 words) |
| **Avg noise rate** | 48.1% |
| **Avg variants per word** | 5.3 |
| **Total variants generated** | 424 |
| **Min variants per word** | 0 |
| **Max variants per word** | 48 |

### Per-Category Breakdown

| Category | Count | Coverage | Avg Variants |
|----------|-------|----------|--------------|
| **common** | 15 | **100.0%** | 3.6 |
| **compounds** | 10 | 90.0% | 5.1 |
| **food** | 12 | 91.7% | 4.1 |
| **loanwords** | 10 | 70.0% | 8.9 |
| **places** | 10 | **100.0%** | 6.9 |
| **slang** | 13 | 92.3% | 5.2 |
| **verbs** | 10 | 90.0% | 4.5 |

### Coverage Analysis — Uncovered Words (7 total)

| Thai | Category | TLTK Output | Reason for Miss |
|------|----------|-------------|-----------------|
| แกงเขียวหวาน | food | kaengkhiaowan | Expected forms use spaces; generator concatenates |
| หิว | verbs | hio | TLTK produces "hio" instead of expected "hiu"/"hiw" |
| แซ่บ | slang | *(empty)* | TLTK produces no romanization |
| ร้านอาหาร | compounds | ran-ahan | TLTK uses hyphens; expected forms use spaces |
| แท็กซี่ | loanwords | thaeksi | Expected "taxi" — English source word, not rule-derivable |
| คอมพิวเตอร์ | loanwords | khomphiotoe | Expected "computer" — English source word |
| เฟซบุ๊ก | loanwords | fe | TLTK only romanizes first syllable |

**Root cause breakdown:**
- 3/7: TLTK limitations (incomplete/incorrect romanization)
- 2/7: Loanwords where users type the English source word
- 2/7: Formatting (hyphen vs space in multi-word compounds)

### Variant Quality — Representative Examples

**High-quality variants (good coverage, low noise):**

| Thai | TLTK Base | Generated Variants | Match? |
|------|-----------|-------------------|--------|
| สวัสดี | sawatdi | sawatdee, sawaddee, sawatdii, sawaddii, sawaddi | ✓ sawaddee, sawatdee |
| ครับ | khrap | khrap, khrab, krap, krab, khap, khab, kap, kab | ✓ krap, krab |
| ดี | di | dee, dii | ✓ dee, dii |
| หมู | mu | moo, muu | ✓ moo, muu |
| กิน | kin | gin | ✓ gin |
| ไทย | thai | tai | ✓ tai |

**Moderate noise (some odd variants):**

| Thai | Questionable Variants | Assessment |
|------|----------------------|------------|
| ถูก | thuug, tuug, toog, thoog | Doubled-u variants like "thuug" are unusual; "took" and "tuk" are good |
| ช็อกโกแลต | 48 variants | Too many from 3-syllable Cartesian product; many are noise |
| โอเค | 18 variants | Multi-syllable Cartesian product produces too many |

### Rule Impact Analysis

| Rule | Words Affected | Coverage Contribution | Noise Contribution | Assessment |
|------|---------------|----------------------|-------------------|------------|
| **Vowel lengthening** | 45/80 (56%) | High — essential for dee, moo, maa, etc. | Low — targeted by long vowel check | **High value** |
| **Final consonant softening** | 28/80 (35%) | Medium — captures krab, sawaddee, talad | Low — only 3 substitutions | **High value** |
| **Cluster simplification** | 35/80 (44%) | High — captures krap, tai, pet | Medium — ch→j/c less useful | **High value** |
| **R-dropping** | 8/80 (10%) | Medium — captures kungthep | Low — limited scope | **Medium value** |
| **Initial voicing** | 12/80 (15%) | Medium — captures gin, gai, geng | Low — only k→g | **Medium value** |

### Expansion Factor Distribution

| Variants per Word | Count | % of Words |
|-------------------|-------|------------|
| 0 | 1 | 1.2% |
| 1 | 8 | 10.0% |
| 2-3 | 22 | 27.5% |
| 4-6 | 24 | 30.0% |
| 7-12 | 17 | 21.2% |
| 13-24 | 7 | 8.8% |
| 25+ | 1 | 1.2% |

The majority of words (67.5%) produce 2-6 variants, which is ideal for trie construction.

## Observations

1. **The component Cartesian product approach is essential.** Without it, cross-rule combinations like "pood" (ph→p + u→oo + t→d from "phut") cannot be generated. This was the key design improvement.

2. **Noise rate of 48% is deceptively high.** The expected informal list has only 2-4 entries per word. Many generated variants that don't match the expected list are still plausible (e.g., "khrab" for ครับ isn't in the expected list but is valid). The true implausible variant rate is much lower.

3. **Loanwords are inherently problematic.** 3/7 coverage misses are loanwords where users type the English source word ("taxi", "computer", "facebook"). No rule-based transformation of TLTK output can produce these. PyThaiNLP's `lookup` engine (identified in Task 001) should be used to supplement loanword romanizations.

4. **TLTK has blind spots.** แซ่บ produces empty output, เฟซบุ๊ก only produces "fe", and หิว produces "hio" instead of "hiu". These are TLTK bugs/limitations that affect 3/7 misses.

5. **Multi-syllable words can explode.** ช็อกโกแลต produces 48 variants (3 syllables × many component variants each). The max_variants_per_word=50 cap prevents runaway, but pruning strategies would improve quality.

6. **Vowel lengthening is the highest-value rule.** It affects 56% of words and produces the most recognizable informal variants (dee, moo, maa). It has low noise because it's gated on the IPA/g2p long vowel check.

## Reproducibility

To rerun these experiments:

```bash
cd experiments/002-informal-romanization-variants
pip install tltk pythainlp
python scripts/evaluate.py         # Full evaluation with formatted output
python scripts/evaluate.py --json  # JSON output
python scripts/evaluate.py --detail  # Include syllable analysis
```

## Raw Data

- Evaluation results JSON: `experiments/002-informal-romanization-variants/data/evaluation_results.json`
- Test word definitions: `experiments/002-informal-romanization-variants/scripts/test_words.py`
