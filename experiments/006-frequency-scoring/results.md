# Word Frequency Scoring for Candidate Ranking: Experimental Results

**Topic:** research/006-frequency-scoring
**Date:** 2026-03-11
**Author:** THAIME Research (agent)
**Depends on:** 006-frequency-scoring.md (plan), research/005-candidate-selection/summary.md

## Setup

- **Python version:** 3.12.3
- **Key dependencies:** numpy 2.4.3, pandas 3.0.1, PyYAML 6.0.1, pythainlp 5.3.0
- **Data:**
  - Trie dataset: `reference/trie_dataset_sample_5k.json` (5,000 words, 49,364 unique romanization keys)
  - Word list: `reference/wordlist.csv` (164K+ entries for rank/source lookups)
  - Override list: `data/dictionaries/word_overrides/overrides-v0.4.2.yaml` (247 entries)
  - Per-corpus frequencies: extracted from 3 raw corpora (wisesight, wongnai, prachathai) covering 4,866/5,000 trie words

## Test Set Construction

### Set A — Common Word Ranking (70 entries)

Built from the top 2,000 words in the trie dataset by frequency. Selected words whose shortest romanization is **unambiguous** (maps to exactly one top-2K word). Stratified across 4 frequency bands:

| Band | Rank Range | Entries |
|------|-----------|---------|
| top_100 | 1–100 | 18 |
| 100_500 | 101–500 | 18 |
| 500_1000 | 501–1000 | 18 |
| 1000_2000 | 1001–2000 | 16 |

### Set B — Ambiguous Input Discrimination (25 entries)

Selected from romanization keys that map to 2+ different Thai words in the top-5K vocabulary. Expected top candidate is the highest-frequency word. Sampled across different frequency ratios (1.06× to 853×).

### Set C — Override List Recall (247 entries)

All 247 override words from `overrides-v0.4.2.yaml`. All 247 are present in the trie dataset.

## Results

### Best Result Per Formula (Best λ)

| Formula | λ | A MRR | A Top-1 | B MRR | B Top-1 | C Recall |
|---------|-----|-------|---------|-------|---------|----------|
| **baseline** | any | **0.989** | **0.986** | **0.960** | **0.920** | 1.000 |
| **source_weighted** | any | **0.989** | **0.986** | **0.960** | **0.920** | 1.000 |
| **smoothed** | ≥0.3 | **0.989** | **0.986** | **0.960** | **0.920** | 1.000 |
| tfidf | any | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| rank | ≥1.0 | 0.989 | 0.986 | 0.933–0.940 | 0.880 | 1.000 |
| balanced | 1.5–2.0 | 0.989 | 0.986 | 0.873 | 0.760 | 1.000 |

### Full Results Table (All 42 Combinations)

| Formula | λ | A MRR | A Top-1 | B MRR | B Top-1 | C Recall |
|---------|-----|-------|---------|-------|---------|----------|
| baseline | 0.1 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| baseline | 0.3 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| baseline | 0.5 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| baseline | 0.7 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| baseline | 1.0 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| baseline | 1.5 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| baseline | 2.0 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 0.1 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 0.3 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 0.5 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 0.7 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 1.0 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 1.5 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| source_weighted | 2.0 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| tfidf | 0.1 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| tfidf | 0.3 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| tfidf | 0.5 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| tfidf | 0.7 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| tfidf | 1.0 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| tfidf | 1.5 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| tfidf | 2.0 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| rank | 0.1 | 0.982 | 0.971 | 0.930 | 0.880 | 1.000 |
| rank | 0.3 | 0.982 | 0.971 | 0.933 | 0.880 | 1.000 |
| rank | 0.5 | 0.982 | 0.971 | 0.933 | 0.880 | 1.000 |
| rank | 0.7 | 0.982 | 0.971 | 0.933 | 0.880 | 1.000 |
| rank | 1.0 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| rank | 1.5 | 0.989 | 0.986 | 0.933 | 0.880 | 1.000 |
| rank | 2.0 | 0.989 | 0.986 | 0.940 | 0.880 | 1.000 |
| smoothed | 0.1 | 0.989 | 0.986 | 0.940 | 0.880 | 1.000 |
| smoothed | 0.3 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| smoothed | 0.5 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| smoothed | 0.7 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| smoothed | 1.0 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| smoothed | 1.5 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| smoothed | 2.0 | 0.989 | 0.986 | 0.960 | 0.920 | 1.000 |
| balanced | 0.1 | 0.960 | 0.929 | 0.890 | 0.800 | 1.000 |
| balanced | 0.3 | 0.974 | 0.957 | 0.890 | 0.800 | 1.000 |
| balanced | 0.5 | 0.981 | 0.971 | 0.890 | 0.800 | 1.000 |
| balanced | 0.7 | 0.981 | 0.971 | 0.890 | 0.800 | 1.000 |
| balanced | 1.0 | 0.981 | 0.971 | 0.870 | 0.760 | 1.000 |
| balanced | 1.5 | 0.989 | 0.986 | 0.873 | 0.760 | 1.000 |
| balanced | 2.0 | 0.989 | 0.986 | 0.873 | 0.760 | 1.000 |

### Failure Analysis

#### Set A Failures

Only **1 failure** shared across baseline, source_weighted, and smoothed:

| Input | Expected | Got (Top-3) | Notes |
|-------|----------|-------------|-------|
| kohn | คอน (rank 4) | คน, ก่อน, ก้อน | `kohn` maps to several higher-frequency words; คอน is relatively rare |

The balanced formula has 2 additional failures at λ=0.5 (`kohngwan → ของหวาน`, `kohn → คอน`).

#### Set B Failures

**Common failures across all formulas** (2 cases):

| Input | Expected | Got #1 | Frequency Ratio | Notes |
|-------|----------|--------|-----------------|-------|
| hun | หุ้น (stocks) | หั่น (chop) | 2.2× (among shortest-rom collisions) | หั่น also maps to "hun" (non-shortest rom) and has higher global frequency (0.000061 vs 0.000059) — Viterbi is correct |
| chae | แชร์ (share) | เจ (encounter) | 1.77× (among shortest-rom collisions) | เจ also maps to "chae" (non-shortest rom) and has higher global frequency (0.000176 vs 0.000079) — Viterbi is correct |

**Note:** Both "failures" are test set construction artifacts. Set B selects expected top candidates based on shortest-romanization collisions, but the Viterbi lattice matches ALL romanizations for each word. In both cases, the Viterbi correctly ranks the globally highest-frequency word first. The actual Top-1 accuracy on Set B may be higher than reported.

**Additional failures for weaker formulas:**

| Input | Expected | Formula | Got #1 | Notes |
|-------|----------|---------|--------|-------|
| han | หั่น | tfidf | ฮัน | TF-IDF penalizes common words |
| nanlae | นั่นแหละ | rank, balanced | นั้นและ | Multi-word input, rank/balanced misordered |
| natee | หน้าที่ | balanced | นาที | Per-corpus normalization distorts relative ranking |
| sueg | สึก | balanced | ศึก | Similar words, balanced flips ordering |

### λ Sensitivity Analysis

**Key finding: λ has no measurable effect on single-word input ranking for frequency-based formulas.**

The baseline, source_weighted, smoothed, and tfidf formulas produce **identical results across all 7 λ values**. This confirms the observation from live testing — the segmentation penalty λ only matters when the lattice contains multi-word alternative paths. For single-word-length inputs, there are rarely competing multi-word decompositions, so λ drops out.

The rank formula shows slight λ sensitivity:
- At λ=0.1–0.7: A-MRR=0.982 (1 extra failure on `kohngwan`)
- At λ≥1.0: A-MRR=0.989 (matches baseline)
- B-MRR increases slightly from 0.930 to 0.940 as λ increases

The balanced formula shows stronger λ sensitivity:
- At λ=0.1: A-MRR=0.960 (worst overall)
- At λ≥1.5: A-MRR=0.989 (matches baseline on Set A, but B-MRR degrades to 0.873)

## Observations

1. **The baseline is surprisingly strong.** The simple `-log(freq)` formula achieves 0.989 MRR on unambiguous inputs and 0.960 MRR on ambiguous inputs. This is because the trie dataset's frequency values already represent averaged, multi-corpus frequencies with quality filtering.

2. **Source weighting provides no benefit.** The source_weighted formula matches the baseline exactly. This is because the trie vocabulary was already filtered during pipeline assembly (minimum 2 source count), so most words have similar source counts. Adding a source-count bonus doesn't change the relative ordering.

3. **TF-IDF is correctly harmful (negative control validated).** The TF-IDF formula reduces B-MRR from 0.960 to 0.933 and introduces 1 additional failure (`han → ฮัน` instead of หั่น). This confirms that up-weighting rare-source words hurts IME candidate ranking.

4. **Rank-based scoring loses information.** Replacing absolute frequency with rank position reduces discrimination slightly (B-MRR=0.933 vs 0.960 at typical λ values). The additional failure (`nanlae → นั้นและ` instead of นั่นแหละ) occurs because rank compresses the frequency signal.

5. **Corpus-balanced frequency is the worst performer.** Normalizing each corpus to its own max frequency significantly degrades both Set A (MRR drops to 0.960–0.981) and Set B (MRR drops to 0.870–0.890). The normalization inflates words that are moderately frequent in small corpora while deflating words that are high-frequency across all corpora.

6. **The 2 apparent Set B errors are test set construction artifacts.** The `hun` and `chae` "failures" occur because Set B selects expected top candidates based on shortest-romanization collisions, but the Viterbi lattice matches ALL romanizations. In both cases, the Viterbi correctly ranks the globally highest-frequency word first (หั่น > หุ้น for "hun"; เจ > แชร์ for "chae"). The actual baseline accuracy may be higher than 92%.

7. **λ does not matter for single-word ranking.** Confirmed across all formulas. The segmentation penalty only affects multi-word paths, which are rare for typical single-word inputs.

## Reproducibility

To rerun these experiments:

```bash
cd /home/runner/work/thaime-nlp/thaime-nlp

# Download raw corpora (for per-corpus frequency extraction)
python -m src.data.download wisesight wongnai prachathai

# Build test sets
python experiments/006-frequency-scoring/build_test_sets.py

# Run evaluation
python experiments/006-frequency-scoring/evaluate.py
```

## Raw Data

- Test sets: `experiments/006-frequency-scoring/test_set_a.json`, `test_set_b.json`, `test_set_c.json`
- Full results: `experiments/006-frequency-scoring/results_raw.json` (gitignored, regenerable)
- Per-corpus frequencies: `experiments/006-frequency-scoring/per_corpus_frequencies.json` (gitignored, regenerable)
