# Smoke Test

Release validation harness that checks whether pipeline artifacts (trie dataset + n-gram binary) produce correct candidate rankings. It reimplements the thaime engine's candidate selection logic in Python (see `docs/engine-scoring.md`) and runs known-answer test cases against the generated data.

## Usage

```bash
python -m pipelines smoke-test
python -m pipelines smoke-test --data-dir pipelines/outputs --beam-width 10
```

**Prerequisites:** Pipeline artifacts must exist in the data directory:
- `<data-dir>/trie/trie_dataset.json` — from `python -m pipelines trie run`
- `<data-dir>/ngram/thaime_ngram_v*_mc*.bin` — from `python -m pipelines ngram encode`

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--data-dir` | `pipelines/outputs` | Path to pipeline outputs directory |
| `--test-cases` | bundled `test_cases.yaml` | Path to custom test cases file |
| `--beam-width` | 10 | K parameter for Viterbi search |

### Output

Each test case reports one of three statuses:

- **PASS** — expected output is rank 1
- **WARN** — expected output is in top-K but not rank 1
- **FAIL** — expected output not found in top-K

The command exits with code 1 if any test case fails. Warnings do not cause failure.

## Architecture

The smoke test is a four-module Python package at `src/utils/smoke_test/`:

| Module | Engine Stage | Description |
|--------|-------------|-------------|
| `trie_lookup.py` | Stage 1: Prefix search | Loads `trie_dataset.json`, builds a prefix index, returns lattice edges via `TrieData.prefix_match()` |
| `ngram_score.py` | Stage 3: N-gram scoring | Parses TNLM v1 binary, provides Stupid Backoff scoring via `NgramModel.trigram_score()` returning linear probabilities |
| `viterbi.py` | Stage 2: Viterbi k-best | Position-based forward pass with cost-based scoring via `beam_search()`, matching the engine's formula and pruning strategy |
| `__init__.py` | Orchestration | Loads artifacts, runs test cases through the pipeline, reports results |

The CLI entry point is `pipelines/__main__.py` (the `smoke-test` subcommand).

For scoring formula details and parameters, see `docs/engine-scoring.md`.

## Test Cases

Test cases are defined in `src/utils/smoke_test/test_cases.yaml`. Each entry has:

```yaml
- input: "malongchaithaime"
  expected: "มาลองใช้ไทยมี"
  note: "Web demo flagship phrase"
```

| Field | Required | Description |
|-------|----------|-------------|
| `input` | yes | Latin romanization string (spaces are stripped) |
| `expected` | yes | Expected Thai output at rank 1 |
| `note` | no | Free-text annotation |

### Current Test Cases

| Input | Expected | Notes |
|-------|----------|-------|
| `thaime` | ไทยมี | Single compound word |
| `malongchaithaime` | มาลองใช้ไทยมี | Flagship demo phrase, multi-word Viterbi |
| `sawasdeekrub` | สวัสดีครับ | Common greeting |
| `sawatdeekrub` | สวัสดีครับ | Alternate romanization of the same greeting |
| `pimthaimaidai` | พิมพ์ไทยไม่ได้ | Negative phrase with ไม่ได้ |
| `pimthaidailaew` | พิมพ์ไทยได้แล้ว | Positive phrase with ได้แล้ว |
| `kuenrodklabban` | ขึ้นรถกลับบ้าน | Verb phrase |
| `jerkunprungneekrab` | เจอกันพรุ่งนี้ครับ | Future time reference |

### Adding Test Cases

Add entries to `test_cases.yaml`. Guidelines:

- Choose inputs where the expected output is unambiguously the best candidate
- Multi-word phrases are more valuable than single words (they exercise n-gram scoring and Viterbi)
- Include a `note` if the case tests a specific behavior (e.g., romanization variant, particle disambiguation)

## Relationship to Engine

The smoke test is a **Python reimplementation** of the Rust engine's candidate selection, not a test of the pipeline code itself. Its purpose is to validate that the pipeline's output artifacts (trie + n-gram binary) produce correct rankings when fed through the same algorithm the engine uses.

If a test case fails, the cause is one of:
1. **Pipeline bug** — the generated data is wrong (bad frequencies, missing words, corrupted binary)
2. **Smoke test bug** — the Python reimplementation diverges from the engine
3. **Test case bug** — the expected output is wrong for the current data

Minor score differences between the smoke test and the Rust engine are expected due to f32/f64 precision differences. The smoke test only checks rank ordering, not exact score values.
