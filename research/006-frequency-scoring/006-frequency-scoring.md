# Research Plan 006: Word Frequency Scoring for Candidate Ranking

**Branch:** `research/006-frequency-scoring`
**Status:** DRAFT
**Estimated effort:** 1–2 days (agent-executable)

## Research Question

Which word frequency scoring formula produces the best candidate ranking in THAIME's Viterbi path search, given the current multi-corpus word frequency data?

## Motivation

The current scoring model uses raw normalized frequency: `cost(word) = -log(freq)`, where `freq` is a simple average across corpora where the word appears. This has known problems:

1. **Corpus bias.** Equal-weight averaging means domain-specific words are over-promoted: ร้าน (shop) is inflated by Wongnai (restaurant reviews), รัฐบาล (government) is inflated by Prachathai (news). A general-purpose IME should score these according to general Thai usage, not according to whichever corpus mentions them most.

2. **Poor discrimination in the middle frequency range.** The top 100 and bottom 1000 words are easy — high-frequency words are obviously common, garbage is obviously rare. The problem is the thousands of words in the middle where raw frequency gives near-identical scores, making candidate ranking essentially random.

3. **No source reliability signal.** A word appearing in 4/5 corpora with moderate frequency in each is almost certainly a real, commonly-used word. A word appearing in 1 corpus with high frequency might be domain jargon. The current formula doesn't distinguish these.

4. **Segmentation penalty is untuned.** The λ=0.5 penalty was set on synthetic data in Research 005. Live testing with the real trie dataset suggests the segmentation penalty has minimal effect on candidate ranking — it is currently defaulted to λ=1.0. It still needs systematic evaluation to confirm.

## Approach

### Phase 1: Build the evaluation test set

Construct a test set of romanization inputs with expected Thai outputs, drawn from three sources:

**Set A — Common word ranking (50–80 entries).** Select high-frequency words from the curated trie vocabulary (top 2K by frequency) that have clear, unambiguous romanization inputs. For each, record `(romanization_input, expected_thai_word)`. These test whether the scoring formula ranks the obvious answer first.

How to build Set A:
1. Load the trie dataset (`experiments/006-frequency-scoring/reference/trie_dataset_sample_5k.json`)
2. Filter to words in the top 2K by frequency
3. For each word, pick the shortest/most natural romanization variant as the test input
4. Exclude words whose romanization input collides with other top-2K words (ambiguous inputs make ranking evaluation noisy)
5. Sample ~70 words stratified across frequency bands (top-100, 100–500, 500–1000, 1000–2000)

**Set B — Ambiguous input discrimination (20–30 entries).** Select romanization keys that map to 2+ Thai words in the trie (collisions). For each, record `(romanization_input, expected_top_candidate, other_valid_candidates)`. Use frequency rank as the tiebreaker for expected top candidate — the more common word should generally rank first.

How to build Set B:
1. Load the collision report from the trie dataset
2. Filter to collisions where both/all Thai words are in the top 5K vocabulary
3. For each collision, the expected top candidate is the highest-frequency word
4. Select 20–30 collisions spanning different frequency ratios (10:1, 3:1, near-equal)

**Set C — Override list recall (supplementary).** Use the override list (`data/dictionaries/word_overrides/overrides-v0.4.2.yaml`) as a recall test — do these words appear in the candidate list at all? This doesn't test ranking (overrides are edge cases), but ensures scoring changes don't accidentally suppress override words.

### Phase 2: Implement scoring formulas

Implement 5–6 scoring formulas that can be swapped into the Viterbi scorer. Each formula computes `cost(word) → float` (lower is better).

**Formula 1: Current baseline — raw frequency.**
```
cost(word) = -log(freq_avg)
where freq_avg = mean(freq_corpus for corpus where word appears)
```
This is the current implementation.

**Formula 2: Source-count weighted frequency.**
```
cost(word) = -log(freq_avg) - α × log(source_count / total_sources)
```
Words appearing in more corpora get a bonus. The intuition: a word in 4/5 corpora is more likely to be generally useful than a word in 1/5 corpora, even at the same frequency. α is a tunable mixing weight (start with α=1.0).

**Formula 3: TF-IDF inspired.**
```
cost(word) = -log(freq_avg × idf(word))
where idf(word) = log(total_sources / source_count)
```
This is the inverse of Formula 2's direction — it *up-weights* words that are distinctive to fewer corpora. TF-IDF is designed for document retrieval (finding distinguishing terms), which is the opposite of what an IME wants (finding common terms). Including it as a negative control confirms that the source-count bonus in Formula 2 is doing useful work, not just adding noise.

**Formula 4: Rank-based scoring.**
```
cost(word) = log(rank)
where rank = position in frequency-sorted vocabulary (1 = most frequent)
```
Ignores absolute frequency entirely. Uses only relative ordering. This is robust to corpus size differences and domain bias — the rank of คน (person) is stable across corpora even if its absolute frequency varies by 10×. Known to work well in Zipfian distributions (which word frequencies follow).

**Formula 5: Log-smoothed frequency with source bonus.**
```
cost(word) = -log((freq_avg + δ) / (1 + δ × vocab_size)) - β × log(source_count)
where δ = smoothing constant (e.g., 1e-6)
      β = source weight (tunable)
```
Adds Laplace-style smoothing to handle zero/near-zero frequencies more gracefully, plus an independent source-count term. This separates the "how frequent is this word" signal from the "how reliable is this frequency estimate" signal.

**Formula 6: Corpus-balanced frequency.**
```
freq_balanced = Σ_corpus (freq_in_corpus / max_freq_in_corpus) / num_corpora_where_present
cost(word) = -log(freq_balanced)
```
Normalizes each corpus's frequency to its own scale before averaging. This prevents a single large corpus (e.g., Wikipedia) from dominating the frequency estimates.

### Phase 2.5: Extract per-corpus frequency data

The trie dataset only contains the merged `frequency` — per-corpus breakdowns are discarded during pipeline assembly. To enable Formula 6 (and enrich the data available to all formulas), extract per-corpus frequencies directly from the raw corpora before running the evaluation.

**How to extract per-corpus frequencies:**
1. Use the existing corpus reader functions in `pipelines/trie/wordlist.py`:
   - `read_wongnai()` → returns `Counter` of raw token counts from Wongnai reviews
   - `read_wisesight()` → returns `Counter` of raw token counts from Wisesight social media
   - `read_prachathai()` → returns `Counter` of raw token counts from Prachathai news
   - (Optional: `read_thwiki()`, `read_pythainlp()` — thwiki is slow to parse, pythainlp is a word list not a corpus)
2. Normalize each corpus's raw counts to frequencies: `freq = count / total_tokens`
3. For each word in the trie vocabulary, record the per-corpus normalized frequencies
4. Save as an intermediate file (e.g., `experiments/006-frequency-scoring/per_corpus_frequencies.json`)

The three priority corpora are **wongnai**, **wisesight**, and **prachathai** — these represent informal reviews, informal social media, and formal news respectively, giving good domain diversity. Download the raw data first:
```
python -m src.data.download wongnai wisesight prachathai
```
This downloads to `data/corpora/raw/{corpus_name}/` (gitignored). Wongnai is ~60 MB, Wisesight ~5 MB, Prachathai ~242 MB.

**Important:** The corpus readers depend on PyThaiNLP tokenization, which can take a few minutes per corpus. Cache the results so re-runs are fast.

### Phase 3: Evaluate

For each scoring formula (and for several values of any tunable parameters):

1. **Build the word lattice** for each test input using the real trie dataset.
2. **Run Viterbi** with the candidate formula and k=10.
3. **Measure:**
   - **MRR (Mean Reciprocal Rank)** on Set A: Where does the expected word rank? MRR = mean(1/rank). Perfect score = 1.0.
   - **MRR on Set B**: Same metric, but on ambiguous inputs.
   - **Top-1 accuracy** on Sets A and B: What fraction of test inputs have the expected word as the #1 candidate?
   - **Recall on Set C**: What fraction of override words appear somewhere in the top-10 candidates?

4. **Also sweep λ (segmentation penalty)** for each formula. Test λ ∈ {0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0}. Report the best λ for each formula. Note: live testing suggests λ has minimal effect on ranking — the sweep may confirm this, which is itself a useful finding. Default to λ=1.0 for the baseline.

### Phase 4: Analysis

1. Rank formulas by MRR on Set A (primary metric).
2. Check if Set B rankings change — does any formula improve disambiguation?
3. Identify failure cases: inputs where all formulas give wrong top-1.
4. Report the recommended formula + λ value, with confidence intervals if feasible.

## Deliverables

1. **Test set files:**
   - `experiments/006-frequency-scoring/test_set_a.json` — common word ranking test set
   - `experiments/006-frequency-scoring/test_set_b.json` — ambiguous input test set
   - `experiments/006-frequency-scoring/test_set_c.json` — override recall test set

2. **Scoring implementations:**
   - `experiments/006-frequency-scoring/scoring.py` — all 6 formulas as pluggable functions

3. **Evaluation script:**
   - `experiments/006-frequency-scoring/evaluate.py` — runs all formulas on all test sets, outputs metrics table

4. **Summary:**
   - `research/006-frequency-scoring/summary.md` — findings, recommendation, failure analysis

## Prerequisites

- Trie dataset at `experiments/006-frequency-scoring/reference/trie_dataset_sample_5k.json` (from CP05/CP07)
- Word frequency data (embedded in trie dataset or in `experiments/006-frequency-scoring/reference/wordlist.csv`)
- Raw corpora at `data/corpora/raw/` — **must be downloaded** before Phase 2.5. Run: `python -m src.data.download wongnai wisesight prachathai`
- Corpus reader functions in `pipelines/trie/wordlist.py` — `read_wongnai()`, `read_wisesight()`, `read_prachathai()` etc.
- Candidate selection prototype code from Research 005 — **copied to this branch at `experiments/006-frequency-scoring/reference/candidate_selection_r005.py`**
- Override list at `data/dictionaries/word_overrides/overrides-v0.4.2.yaml`
- Python environment with numpy, pandas (for analysis)

## Scope Boundaries

**In scope:**
- Comparing unigram scoring formulas
- Tuning the segmentation penalty λ
- Building reusable test sets for future scoring evaluations

**Out of scope:**
- Bigram/N-gram scoring (future research)
- Romanization confidence weights (future work, tied to variant generator)
- Changes to the Viterbi algorithm itself
- Changes to the trie data or variant generator
- Engine-repo (Rust) changes

## Notes for the Executing Agent

### Getting started

1. Start by reading the existing codebase. Key files:
   - `experiments/006-frequency-scoring/reference/candidate_selection_r005.py` — the R005 Viterbi prototype (copied onto this branch for convenience). Uses mock data — you need to adapt it to load the real trie dataset.
   - `experiments/006-frequency-scoring/reference/test_cases_r005.py` — R005 test cases (for reference, not direct reuse)
   - `experiments/006-frequency-scoring/reference/trie_dataset_sample_5k.json` — the real trie data (8K vocab, 94K romanization keys)
   - `experiments/006-frequency-scoring/reference/wordlist.csv` — full 164K word frequency data with rank, source_count, and sources columns
   - `data/dictionaries/word_overrides/overrides-v0.4.2.yaml` — override word list

2. **Trie dataset schema.** Each entry in `trie_dataset_sample_5k.json` has: `word_id`, `thai`, `frequency` (pre-normalized 0–1), `sources` (list of corpus names), `romanizations` (list of strings). Note: there is no `rank`, `source_count`, or `per_corpus_frequencies` field — derive `source_count` from `len(sources)` and `rank` from sorting by frequency.

3. The `wordlist.csv` has pre-computed `rank` and `source_count` columns and can be used as a convenient alternative for frequency/rank lookups.

4. **Per-corpus frequency data** is not in the trie dataset but can be extracted from the raw corpora. The corpus reader functions in `pipelines/trie/wordlist.py` (`read_wongnai()`, `read_wisesight()`, `read_prachathai()`, etc.) each return a `Counter` of raw token counts. These are the same functions used by the trie pipeline — call them directly to get per-corpus breakdowns. The raw corpora are already downloaded at `data/corpora/raw/`. See Phase 2.5 in the Approach section.

### Building the test sets

- For Set A, the key quality criterion is *unambiguous inputs*. If a romanization key maps to 3 Thai words, it belongs in Set B, not Set A. Filter these out.
- For Set B, prefer collisions between words of *different* frequency tiers — a collision between the #50 and #5000 word is a better test of scoring discrimination than a collision between #50 and #55.
- For Set C, just load the override YAML and extract the Thai words. No curation needed.
- Export all test sets as JSON with clear schemas. Include metadata (how the set was built, filter criteria, date).

### Implementing scoring formulas

- All formulas should have the same function signature: `def cost(word_id, word_data, **params) -> float`
- The `word_data` dict should contain: `frequency`, `source_count` (derived from `len(sources)`), `rank` (derived from frequency sort), and `per_corpus_frequencies` (extracted in Phase 2.5 — a dict mapping corpus name to normalized frequency).
- Tunable parameters (α, β, δ, λ) should be passed as keyword arguments so the evaluation script can sweep them easily
- Include the current baseline (Formula 1) exactly as-is, so the comparison is fair

### Running the evaluation

- For each formula × parameter combination × test input, run Viterbi and record the full top-10 candidate list
- Store raw results (not just metrics) so that failure analysis is possible after the fact
- If running all combinations is slow, prioritize Set A with all formulas first, then Set B

### Writing the summary

- Lead with the recommendation: which formula, which λ, how much improvement over baseline
- Include a table comparing all formulas on both MRR and Top-1 accuracy
- Identify the most informative failure cases — inputs where scoring clearly matters
- Note any surprising results (e.g., if TF-IDF actually helps despite theoretical expectations)
- Keep the summary concise — this is a focused evaluation, not a literature survey

### Common pitfalls

- Make sure frequency values are loaded correctly from the trie dataset. The `frequency` field is already normalized (0–1 range). Don't normalize twice.
- The Viterbi prototype from R005 uses a mock dictionary with made-up frequencies. You need to replace the dictionary loading, not just the cost function.
- When building lattices from the real trie, a single romanization input may have hundreds of prefix matches. This is expected — the lattice can be large. If performance is an issue, cap the lattice size per the R005 recommendation.
- The segmentation penalty λ and the scoring formula interact. Always report results as (formula, λ) pairs, not formula alone.
- Live testing so far suggests λ has minimal effect on candidate ranking. The default is λ=1.0. If the sweep confirms this, report it as a finding — it simplifies the final recommendation.

## References

- Research 005: Candidate Selection Algorithm — `research/005-candidate-selection/summary.md`
- CP05: Trie Generation Pipeline — `docs/plans/change-plan-05-trie-pipeline.md`
- CP07: Trie Quality — `docs/plans/change-plan-07-trie-quality.md`
- SentencePiece unigram model — uses similar `-log(freq) + penalty` scoring
- Zipf's law — theoretical basis for rank-based scoring (Formula 4)