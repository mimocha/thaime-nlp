# Google Input Tools Thai: Experimental Plan

**Topic:** research/009-google-input-tools
**Date:** 2026-07-12
**Author:** Chawit Leosrisook (maintainer) + Claude (agent)
**Depends on:** hypothesis.md

## Objective

Measure THAIME's conversion quality against Google Input Tools (a production Latin-to-Thai
reference) on a shared test set, localize where THAIME loses (segmentation / ranking /
vocabulary / coverage), and — as a byproduct of the same runs — mine Google-accepted
romanization variants THAIME does not generate. The quality comparison is the primary
deliverable; coverage comparison and variant mining are secondary. Frontend/UX
reverse-engineering of Google's extension is **out of scope** (see below).

## Experimental Variables

| Variable | Values | Description |
|----------|--------|-------------|
| System | THAIME (`beam_search`) · Google (`inputtools` API) | The two systems being compared. |
| Input granularity | single-word · multi-word phrase | Whether the input is one word or a full phrase; tests segmentation behavior. |
| Romanization style | RTGS-like · informal | Whether the Latin input follows a transcription standard or how a native speaker actually types. |
| Candidate depth `k` | 5 · 10 | Number of ranked candidates requested/recorded from each system. |
| Phrase length bucket | 1 syll · 2–3 syll · 2–4 words · 5+ words | Controls the difficulty axis for the quality benchmark. |

Held constant: THAIME beam width (10, per R005 `k=10`), THAIME data build (a single pinned
`pipelines/outputs/` release), Google `itc=th-t-i0`.

## Evaluation Metrics

| Metric | Description | How Measured |
|--------|-------------|--------------|
| Top-1 accuracy | Fraction of inputs whose rank-1 candidate is the correct/expected Thai | `#(rank1 == gold) / N`; gold from benchmark label or maintainer judgment |
| Top-5 accuracy | Fraction where the correct Thai appears in the top 5 | `#(gold ∈ top5) / N` |
| MRR | Mean reciprocal rank of the correct Thai | `mean(1 / rank_of_gold)`, 0 if absent |
| Disagreement category | Where THAIME loses relative to Google | Manual/assisted labelling of each loss into: segmentation · ranking · vocabulary (word absent) · coverage (variant not generated) |
| Coverage acceptance (secondary) | Whether each system returns the correct Thai *at all* for a given variant | boolean per (system, variant); aggregated to acceptance rate |
| Variant-mining yield (secondary) | Count of Google-accepted, THAIME-missing romanization variants flagged for review, and count the maintainer accepts | tally after maintainer validation |

Report top-1/top-5/MRR with a bootstrap 95% CI, and always report the *effective*
discriminating-row count (inputs where the two systems actually differ), per R007's warning
that raw N overstates a benchmark's power.

## Datasets

- **Benchmarks used:**
  - `src/utils/smoke_test/test_cases.yaml` — 8 curated end-to-end phrase cases.
  - `benchmarks/word-conversion/v0.4.1.csv` — current word-conversion benchmark (326 words /
    1311 variants originated in v0.1.0; use the current v0.4.1).
  - `benchmarks/ranking/bigram/v0.1.1.csv` — R007's 200-row ranking set (used with its known
    reliability caveats, not as the sole measure).
- **Additional data:**
  - A new phrase set across the four length buckets (see Procedure 2.1), authored to be
    balanced and to avoid R007's failure modes (compound-tokenization contamination,
    dominant-word imbalance).
  - `pipelines/outputs/trie/trie_dataset.json` — frequency-ranked vocabulary (16,566 words,
    ordered by `word_id`) for selecting "top-N" words in the coverage/mining phase.
- **Preprocessing:**
  - THAIME candidates are **deduplicated by Thai output text** (keep best-scoring), per R005
    open-question #4, so multiple romanization variants collapsing to the same Thai do not
    pollute top-5.
  - All Google API responses are cached to `experiments/009-google-input-tools/cache/`
    keyed by exact query; a query is never re-sent.

## Procedure

### Setup (agent-prepared, maintainer-run)

0.1. Agent authors, under `experiments/009-google-input-tools/scripts/`: a cache-everything
Google client (`requests`-based or `google-transliteration-api`) reading a JSON/CSV **query
manifest** and writing per-query JSON to `cache/`; a THAIME runner wrapping
`src/utils/smoke_test/viterbi.py:beam_search` to emit deduped top-k; and analysis notebooks
that read only from `cache/` + THAIME outputs (so metrics recompute offline, no network).
0.2. Maintainer builds a pinned data release: `python -m pipelines trie` and
`python -m pipelines ngram` (or points the runner at a downloaded release artifact) so
`beam_search` has `pipelines/outputs/`.

### Phase 1 — API feasibility + go/no-go gate

1.1. Maintainer runs the validation script against
`inputtools.google.com/request?text={input}&itc=th-t-i0&num={n}`. Confirm it returns Thai
candidates; document the exact response JSON structure, and any metadata/confidence fields.
1.2. Probe practical rate limits (e.g. 10 queries at 1/s, then 100 at varying intervals);
record error responses (429, empty, etc.) and pick a safe delay (≤5 req/s).
1.3. Run the 8 `test_cases.yaml` inputs through the API; record top-5 for each.
1.4. Full-phrase vs single-word probe: compare `pimthaimaidai` (phrase) against `sawatdee`
(word) — does the API segment internally, or expect pre-segmented input? Document.
1.5. **Go/no-go gate.** If the raw endpoint is dead or unusable: fall back to a smaller,
manually/extension-captured comparison set (Phase 2 at reduced N) or stop the scaled
phases and record the negative result. Do not proceed to scaled querying until 1.1–1.2 pass.

### Phase 2 — Quality benchmark (primary)

2.1. Assemble the shared test set: the 8 smoke cases + a sample from
`benchmarks/word-conversion/v0.4.1.csv` (both RTGS-like and informal variants) + a new
balanced phrase set across the four length buckets. Target ≥200 inputs, but prioritize
*effective* discrimination over raw count.
2.2. Run both systems per input: THAIME top-k via `beam_search` (deduped); Google top-5 via
cached API. Maintainer judges, per input, which rank-1 is correct and — when both are
correct — which segmentation is more natural.
2.3. Compute top-1/top-5/MRR (with CIs and effective-row count) for each system, overall and
per variable (granularity, style, length bucket).
2.4. Categorize every THAIME loss into segmentation / ranking / vocabulary / coverage, with
a representative example per category.

### Phase 3 — Coverage comparison + variant mining (secondary)

3.1. From the same cached runs plus targeted queries over the top-N words of
`trie_dataset.json`, bucket each romanization variant as accepted-by-both / THAIME-only /
Google-only.
3.2. Flag high-frequency Google-accepted, THAIME-missing variants; rank by word frequency.
3.3. Maintainer validates flagged variants against native intuition and the v0.5.0
dictionary: is it a variant a Thai speaker would actually type, and does it reveal a gap in
the component rules? Accepted variants feed
`data/dictionaries/component-romanization/dictionary-vX.X.X.yaml` + `CHANGELOG.md`.

## Success Criteria

- **Primary:** a top-1/top-5/MRR comparison of THAIME vs Google on ≥200 inputs, with 95% CIs
  and reported effective-row count, plus a categorized breakdown of every THAIME loss. The
  topic succeeds if it produces a prioritized, evidence-backed list of THAIME's largest gap
  categories (not merely a single aggregate number).
- **Secondary:** ≥20 Google-accepted, THAIME-missing variants surfaced and put to the
  maintainer for review (adoption count reported, not targeted).
- **Artifact:** a reusable cached Google snapshot (`cache/`) for ≥200 inputs, enabling
  offline re-analysis without further API calls.
- A clean go/no-go outcome from Phase 1 is itself a valid result: if the API is unusable, the
  topic concludes with that finding and the smaller fallback comparison.

## Execution Model

- **Agent-prepared, offline:** scripts, query manifests, THAIME runner, and analysis
  notebooks (everything reads from `cache/` + THAIME outputs, so metrics are reproducible
  without network). The agent sandbox has **no network** to `inputtools.google.com`.
- **Maintainer-run, with network:** Phase 1 validation, all scaled API querying, correctness
  and naturalness judgments, and dictionary validation. The maintainer returns cached JSON
  for the agent to analyze.

## Out of Scope (split to `thaime` engine/demo repo)

Reverse-engineering Google's Chrome extension — client-side segmentation, candidate
presentation, pagination, partial-commit mechanics, keyboard UX — is frontend concern that
belongs to the `thaime` engine/demo repo, not this data-research repo. Capture the intent as
a short issue/note there so it is not lost; do not pursue it in R009.

## Ethical & Legal

- `inputtools.google.com` is undocumented; we use it strictly as a research/benchmarking
  snapshot, never as a THAIME runtime dependency.
- Cache all responses; never re-query the same input; keep a reasonable rate limit (≤5 req/s).
- Do not redistribute raw API responses as a dataset, and do not extract Google's dictionary
  or language model. Coverage facts (which input maps to which Thai) are used only to find
  gaps in THAIME's own dictionary.

## Dependencies

```
pip install google-transliteration-api requests   # or a direct requests client
```

- Maintainer environment with network access to `inputtools.google.com`.
- Built `pipelines/outputs/` (run `python -m pipelines trie` + `python -m pipelines ngram`,
  or a downloaded release artifact) so `beam_search` has trie + n-gram data.
- `src/utils/smoke_test/` (`viterbi.py:beam_search`, `trie_lookup.py`, `ngram_score.py`).
- Benchmarks: `benchmarks/word-conversion/v0.4.1.csv`, `benchmarks/ranking/bigram/v0.1.1.csv`,
  `src/utils/smoke_test/test_cases.yaml`.
- `pipelines/outputs/trie/trie_dataset.json` for frequency-ranked word lists.

## Estimated Effort

~3–4 working days. Agent prep (scripts, manifests, notebooks): ~1 day, offline. Phase 1
(feasibility): ~0.5 day, maintainer. Phase 2 (quality benchmark): ~1.5 days including
maintainer judgments. Phase 3 (coverage/mining): ~0.5–1 day. Estimated API volume: a few
thousand cached queries at ≤5 req/s (well under an hour of wall-clock if no rate limiting).
