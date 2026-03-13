# Ranking Benchmark: Bigram Context

Benchmark for evaluating context-dependent candidate ranking in THAIME's IME.
Tests whether bigram (and eventually n-gram) scoring correctly disambiguates
romanization collisions based on preceding word context.

## Format

CSV with columns per `docs/benchmarks.md` ranking spec:

| Column | Type | Description |
|--------|------|-------------|
| `latin_input` | string | Ambiguous romanized input |
| `context` | string | Previously committed Thai word (empty if none) |
| `expected_top` | string | Thai word/phrase that should rank first |
| `valid_alternatives` | string | Pipe-separated other valid candidates |
| `notes` | string | Description; `[repeater]` tag marks ๆ cases |

## Structure

- **No-context baselines**: Entries with empty `context` — the most frequent
  candidate should win (unigram behavior).
- **Context-dependent cases**: Entries with a `context` word — bigram scoring
  should shift the top candidate based on the preceding word.
- **Repeater cases**: Tagged `[repeater]` in notes — aspirational cases for
  future ๆ (mai yamok) handling in the IME. These require repeated-syllable
  detection to produce standalone ๆ as a candidate.

## Metrics

- **MRR (Mean Reciprocal Rank)** — average of 1/rank for `expected_top`
- **Context improvement** — delta MRR between no-context and with-context cases
- **Top-1 accuracy** — % where `expected_top` is the top-ranked candidate

## Romanization Families Covered

`kao`, `mai`, `kan`, `tai`, `kai`, `chao`, `tang`, `pa`, `kum`, `pag`,
`tae`, `cha`, `toh` — plus 4 additional no-context-only families
(`ka`, `chai`, `koh`, `pan`, `tan`, `kohn`).

## Versioning

See [CHANGELOG.md](CHANGELOG.md) for version history.
