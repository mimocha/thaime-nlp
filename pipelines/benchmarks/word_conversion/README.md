# Word-Conversion Benchmark Generation Pipeline

Generates the word-conversion benchmark dataset: a curated set of Thai word → romanization pairs used to evaluate the THAIME engine's conversion accuracy.

## Overview

The pipeline follows a 4-stage flow:

```
Corpus Frequency Extraction → Romanization Generation → Interactive Review → CSV Export
```

1. **Extract** — Read corpora, merge word frequencies, select top-K words.
2. **Romanize** — Generate romanization variants and auto-classify each word.
3. **Review** — Interactive CLI for human review and annotation.
4. **Export** — Output final benchmark as CSV.

## Prerequisites

- **Raw corpora**: Downloaded to `data/corpora/raw/` (wisesight, wongnai, prachathai, thwiki)
- **PyThaiNLP / TLTK**: Available in the devcontainer environment

## Usage

```bash
# Full pipeline (automated steps: extract → romanize)
python -m pipelines benchmark word-conversion run

# Individual steps
python -m pipelines benchmark word-conversion extract     # Step 1
python -m pipelines benchmark word-conversion romanize    # Step 2
python -m pipelines benchmark word-conversion review      # Step 3 (interactive)
python -m pipelines benchmark word-conversion export      # Step 4
```

### Subcommands

#### `word-conversion run`

Runs the automated steps (extract + romanize) in sequence.

```bash
python -m pipelines benchmark word-conversion run
python -m pipelines benchmark word-conversion run --top-k 500
python -m pipelines benchmark word-conversion run --corpora wisesight,wongnai
```

| Option | Description |
|--------|-------------|
| `--corpora` | Comma-separated corpus names (default: wisesight, wongnai, prachathai, thwiki) |
| `--top-k` | Number of top words by frequency (default: 300) |
| `--workers` | Worker processes for romanization (default: 8, 0=sequential) |

#### `word-conversion extract`

Step 1: Extract and merge word frequencies from corpora, output top-K words.

| Option | Description |
|--------|-------------|
| `--corpora` | Comma-separated corpus names |
| `--top-k` | Number of top words (default: 300) |

#### `word-conversion romanize`

Step 2: Generate romanization variants for each word using the variant generator, then auto-classify words (standard, ambiguous, function word).

| Option | Description |
|--------|-------------|
| `--workers` | Worker processes (default: 8, 0=sequential) |

#### `word-conversion review`

Step 3: Interactive terminal-based review tool for annotating benchmark entries. Uses rich for display. Commands include accept/reject, edit romanizations, change classification, and navigate entries.

#### `word-conversion export`

Step 4: Export the reviewed benchmark to CSV format.

## Output Files

All outputs are in `pipelines/outputs/benchmarks/word_conversion/` (gitignored):

| Path | Description |
|------|-------------|
| `word_frequencies.csv` | Intermediate: top-K words with per-corpus frequencies and ranks |
| `draft_benchmark.json` | Intermediate: auto-generated benchmark with romanizations and classifications |
| `reviewed_benchmark.json` | Final: human-reviewed benchmark entries |

## Auto-Classification

Words are automatically classified into categories:

| Category | Description |
|----------|-------------|
| `standard` | Regular Thai words with unambiguous romanization |
| `ambiguous` | Words with known romanization ambiguity (e.g., ร/ล variation) |
| `function_word` | Common function words (particles, conjunctions, etc.) |

The classification informs how strictly the benchmark evaluates engine output.

## Known Limitations

- Interactive review (step 3) requires a terminal — cannot be fully automated
- Auto-classification uses heuristic rules, not exhaustive linguistic analysis
- The benchmark focuses on single-word conversion, not multi-word phrases
