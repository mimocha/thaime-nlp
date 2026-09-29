# Change Plan 12: Romanization Weights and Crowdsourced Data Ingestion

**Date:** 2026-09-29
**Author:** Chawit Leosrisook (maintainer) + Claude (agent)
**Repo:** `mimocha/thaime-nlp` (data side) + `mimocha/thaime` (engine handover)
**Branch:** `pipeline/romanization-weights`
**Status:** Planned. Phases 2–5 depend on data from the crowdsourced typing demo.

## Objective

Give the engine a romanization model, P(Latin | Thai): how likely a given Latin spelling is
for a given Thai word. Learn it from crowdsourced typing data at two levels (whole words and
syllable components), and publish the aggregated data as an open dataset.

## Context

The engine scores each lattice edge as `-ln P(word) + λ + ngram_weight × -ln(context score)`.
It has no romanization term: in `trie_dataset.json` each word's `romanizations` is an
unweighted list, so every spelling of a word counts equally. For example, ที่ has
`tee, thee, thi, thii, ti, tii`.

That list comes from the variant generator (R002/R003, CP04): a Cartesian product of
per-component variants from the component dictionary (v0.5.0), capped at
`max_variants_per_word = 100`. Many of those combinations are spellings nobody would type,
and the cap truncates arbitrarily rather than by likelihood.

Real romanization data has not been available. The crowdsourced typing demo (`thaime` repo,
`docs/plans/crowdsourcing-demo.md`) will collect it: in its contributor mode, users see a
Thai word and type how they would naturally spell it. That measures P(Latin | Thai) directly.

### Two levels of the same distribution

- **Word level:** observed counts per (word, spelling). Precise, but only for words
  contributors actually typed, which will be a few thousand at most.
- **Component level:** probabilities per component variant, e.g. onset ท → `th` / `t`, which
  is the component dictionary with weights. Multiplying through a word's syllables estimates
  P(Latin | Thai) for all ~16.5K words, including ones no contributor has typed.

The component model serves as the prior; word-level counts refine it where data exists.

### Scope

In scope: the weighted data format, the engine handover spec, the crowd-data ingestion
stage, word- and component-level weight estimation, variant pruning by likelihood, and the
published aggregate dataset.

Out of scope: n-gram counts from crowd data (generator text must never be used for n-grams,
and custom text needs separate research), and the demo itself (`thaime` repo).

## Approach

### Phase 1: Weighted data format (no behaviour change)

**Task 1.1 — Schema v2 for `trie_dataset.json`.** Add a per-romanization weight, parallel
to the existing list:

```json
{
  "word_id": 0,
  "thai": "ที่",
  "frequency": 0.015568603625,
  "romanizations": ["tee", "thee", "thi", "thii", "ti", "tii"],
  "romanization_probs": [0.1667, 0.1667, 0.1667, 0.1667, 0.1667, 0.1667]
}
```

`romanization_probs` is P(Latin | Thai), normalized per word. The first release uses uniform
values, since no data exists yet.

**Task 1.2 — Engine handover spec** (for the `thaime` repo, same pattern as
`docs/handover-ngram-binary-v1.md`):

- `thaime_dictgen` reads `romanization_probs` and stores one weight per (key, word) pair
  in the posting lists. If the field is missing, it treats all spellings as equal.
- Edge cost gains a term: `roman_weight × -ln(p / p_max)`, where `p_max` is the word's
  most likely spelling. A new `roman_weight` parameter is added to `RankingParams` and made
  tunable in the TUI.
- **Why relative to `p_max`:** raw `-ln p` would penalize words by how many variants the
  generator produced for them. A word with 100 variants would get `ln 100 ≈ 4.6` extra cost
  under uniform weights, purely from the Cartesian-product size. The relative form costs 0
  for each word's most typical spelling. Uniform weights therefore reproduce today's
  rankings exactly, so Phase 1 ships with no behaviour change.

### Phase 2: Crowd data ingestion stage

**Task 2.1 — `python -m pipelines crowd`.** Input: the SQL dump from
`wrangler d1 export` of the demo's D1 database. Parse batches, check schema and app
versions, and drop malformed ones.

**Task 2.2 — Contributor handling.**

- Count **distinct contributors** per (word, spelling); one contributor counts once.
- Cap how many observations a single contributor ID can add in total, so a heavy
  contributor cannot dominate.
- Drop contributors whose input is mostly unparseable (see 2.3), since that indicates spam
  or someone playing around.

**Task 2.3 — Component parsing.** For each contributor-mode token, try to split the typed
Latin into the word's syllable components, allowing any variant the component dictionary
lists for each component. This is a constrained match over the same decomposition the
variant generator already uses.

- **Parse succeeds:** record the per-component observations, for Phase 4.
- **Parse fails:** it's a novel spelling or noise (typos, internal spaces such as
  `sa wat dee`). It goes to a review queue, and surfaces for the maintainer only once at
  least *k* distinct contributors have typed the same spelling.
- **Multiple parses:** split the observation's count equally across them.

**Task 2.4 — Outputs.**

| Output | Contents | Used by |
|--------|----------|---------|
| Aggregate counts | `thai, word_id, latin, n_contributors, n_observations, in_dictionary` | Phases 3–5 |
| Novel spelling queue | Unparseable spellings with ≥ *k* distinct contributors | Maintainer review, component dictionary updates |
| New-word candidates | Out-of-vocabulary tokens from custom targets, with ≥ *k* distinct contributors | Vocabulary review (overrides) |
| Misconversion reports | THAIME-mode commits that differ from the target, plus explicit marks | Engine and ranking analysis |
| Need list | Words with the fewest distinct contributors, weighted toward common words | Demo's generator (static JSON) |

**Task 2.5 — Data rules.** Every submission carries `target_source` (`generator` or
`custom`). Generator-sourced text is excluded from any n-gram use, enforced here rather than
in the demo. Custom-target text is kept for future n-gram research but not used by this plan.

### Phase 3: Word-level weights

Estimate each word's P(Latin | Thai) with smoothing toward a prior:

```
P(latin | word) = (c(latin, word) + α · prior(latin | word)) / (N_word + α)
```

- `c` is the distinct-contributor count, `N_word` is its sum over the word's spellings, and
  `α` controls how much evidence is needed to move away from the prior.
- The prior is uniform until Phase 4 ships, then the component-level model.
- Novel spellings accepted by the maintainer are added as new keys.

### Phase 4: Component-level weights and pruning

**Task 4.1 — Component probabilities.** From the Phase 2.3 parses, estimate
P(Latin component | Thai component) for every entry in the component dictionary, smoothed so
that listed-but-unobserved variants keep a small floor. Record these as weights in the next
component dictionary version (with a CHANGELOG entry).

**Task 4.2 — Word prior.** Each generated spelling's prior is the product of its components'
probabilities, normalized over the word's spellings. This becomes the Phase 3 prior, giving
every word in the vocabulary non-uniform weights.

**Task 4.3 — Pruning by likelihood.** Replace the arbitrary truncation at
`max_variants_per_word` with keeping the most probable spellings, optionally cutting off
below a probability threshold. This also reduces key collisions between words.

### Phase 5: Published dataset

Publish the Phase 2 aggregate counts as a GitHub Release artifact on this repo, versioned
separately from nlp-data (e.g. `crowd-romanization-v0.1.0`). Rules:

- Aggregates only, never raw submissions or raw custom text.
- A row is published only with at least *k* distinct contributors.
- Include a README covering provenance, collection method, the consent text version, and
  the license.

## Validation

- **Phase 1:** with uniform weights, rankings must be identical to the current release on
  `benchmarks/word-conversion/v0.4.1.csv`, the bigram ranking benchmark, and the smoke tests.
- **Phases 3–4:** hold out a random subset of contributor IDs. On their observations, compare
  top-1 accuracy and MRR of Latin → Thai conversion with and without romanization weights.
  Split by contributor, not by observation, so a person's habits can't leak between train and
  test.
- **Proposed new benchmark:** the held-out crowd data is real-user evidence, which also helps
  the High-priority "Benchmark Reliability" topic. Adding it as a benchmark needs maintainer
  approval (Key Rule 1); existing benchmarks are not modified.

## Acceptance Criteria

- Phase 1: schema v2 released, the engine reads it, and rankings are unchanged under uniform
  weights.
- Phase 2: the ingestion stage runs end-to-end on a real D1 export and produces all five
  outputs.
- Phases 3–4: held-out top-1 and MRR improve over the unweighted baseline, and existing
  benchmarks do not regress.
- Phase 5: the first aggregate dataset is published with a README and a license.

## Task Breakdown

| Phase | Task | Description | Effort | Blocking on |
|-------|------|-------------|--------|-------------|
| 1 | T1.1 | Schema v2 with uniform `romanization_probs` | 0.5 day | — |
| 1 | T1.2 | Engine handover spec + engine implementation (`thaime`) | 1.5 days | T1.1 |
| 2 | T2.1–2.2 | Ingestion stage, validation, contributor handling | 1.5 days | Demo M1 data (can start on synthetic batches) |
| 2 | T2.3 | Component parser for typed Latin | 1.5 days | — |
| 2 | T2.4–2.5 | Outputs, need list, data-rule enforcement | 1 day | T2.1, T2.3 |
| 3 | T3 | Word-level smoothed weights | 1 day | T2.4 |
| 4 | T4.1–4.3 | Component weights, word prior, likelihood pruning | 2 days | T2.3, T3 |
| 5 | T5 | Published aggregate dataset | 0.5 day | T2.4, license decision |
| — | V | Validation (held-out contributors, regression checks) | 1 day | T3/T4 |

**Total estimated effort:** ~10.5 days, spread over time as demo data accumulates.

## Limitations

- **Contributor population bias.** Early contributors will skew toward tech-savvy users, and
  their spelling habits may not represent all Thai typists. Distinct-contributor counting
  limits the effect of heavy contributors but not population skew.
- **Honest-user assumption.** Contributor IDs are random browser-side UUIDs and can be reset.
  Offline filtering catches crude abuse, not careful manipulation.
- **Coverage.** Word-level data will stay sparse for rare words. The need list and the
  component-level prior mitigate this but don't remove it.
- **Parse ambiguity.** Some typed spellings split into components in more than one way. Equal
  splitting is a simplification.

## Open Questions

1. **Cost form.** Is `-ln(p / p_max)` right, or should the engine use raw `-ln p` once the
   variant sets are pruned (Task 4.3)? Decide during Phase 3 validation.
2. **Thresholds.** The minimum distinct contributors *k* for novel spellings, new words, and
   publication; and the smoothing strength `α`.
3. **Default `roman_weight`.** Tune with the TUI and the held-out benchmark.
4. **Dataset license.** CC0 or CC-BY-4.0; the demo's consent text must match.
5. **Other priors.** Should Google-accepted spellings mined in R009 act as a weak extra prior?

## References

- `thaime` repo: `docs/plans/crowdsourcing-demo.md` (data source and collection design)
- Research 002: Informal Romanization Variants — `research/002-informal-romanization-variants/summary.md`
- Research 003: Component Romanization — `research/003-component-romanization/summary.md`
- Research 005: Candidate Selection — `research/005-candidate-selection/summary.md`
- Research 007: N-gram Transition Probability (Benchmark Reliability) — `research/007-bigram-scoring/summary.md`
- Component dictionary — `data/dictionaries/component-romanization/dictionary-v0.5.0.yaml`
- N-gram binary handover (format pattern) — `docs/handover-ngram-binary-v1.md`
