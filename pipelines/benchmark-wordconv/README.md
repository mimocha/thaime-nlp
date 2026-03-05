# Benchmark Word Conversion Pipeline

Generates the `benchmarks/word-conversion/basic.csv` benchmark dataset from Thai NLP corpora.

## Overview

This pipeline extracts the most frequent Thai words from three corpora (wisesight, wongnai, prachathai), generates RTGS romanizations + informal variants using TLTK and the variant generator, then provides an interactive CLI for manual review before exporting to the final benchmark CSV.

## Steps

### Step 1: Extract Word Frequencies

```bash
python -m pipelines.benchmark-wordconv.01_extract_frequencies --top-k 500
```

- Tokenizes all three corpora using PyThaiNLP (`newmm` engine)
- Computes per-corpus word frequencies, normalizes to sum=1.0
- Merges with equal weights (1/3 per corpus)
- Outputs ranked word list to `output/word_frequencies.csv`

**Output:** `output/word_frequencies.csv`

### Step 2: Generate Romanizations + Variants

```bash
python -m pipelines.benchmark-wordconv.02_generate_romanizations --top-k 500
```

- Reads the word frequency list from Step 1
- Runs TLTK `th2roman()` for base RTGS romanization
- Runs the variant generator (`src/variant_generator.py`) for informal variants
- Auto-assigns category (`common`, `ambiguous`, `variant`, `compound`, `edge`) and difficulty (`easy`, `medium`, `hard`) heuristically
- Outputs draft entries to JSON

**Output:** `output/draft_benchmark.json`

### Step 3: Interactive Review CLI

```bash
python -m pipelines.benchmark-wordconv.03_review_cli          # Start fresh
python -m pipelines.benchmark-wordconv.03_review_cli --resume  # Resume previous session
python -m pipelines.benchmark-wordconv.03_review_cli --stats   # Show progress only
```

Interactive terminal UI for reviewing each entry:
- **a** — Approve entry as-is
- **d** — Discard entry
- **e** — Edit entry (category, difficulty, notes, variants)
- **v** — Add/remove specific variants
- **j/k** — Navigate forward/backward
- **p** — Jump to next pending entry
- **t** — Show statistics
- **q** — Save and quit

Progress is saved to `output/reviewed_benchmark.json` and can be resumed.

**Output:** `output/reviewed_benchmark.json`

### Step 4: Export to Benchmark CSV

```bash
python -m pipelines.benchmark-wordconv.04_export_csv                    # Write benchmark
python -m pipelines.benchmark-wordconv.04_export_csv --dry-run          # Preview only
```

- Reads approved + edited entries from the reviewed JSON
- Generates one CSV row per variant per word (each maps a `latin_input` to an `expected_thai`)
- Writes to `benchmarks/word-conversion/basic.csv`

**Output:** `benchmarks/word-conversion/basic.csv`

## Data Sources

| Corpus | Category | Size | Description |
|--------|----------|------|-------------|
| Wisesight | Informal | 26K messages | Social media sentiment corpus |
| Wongnai | Informal | 247K reviews | Restaurant review corpus |
| Prachathai | Formal | 67K articles | News article corpus |

All three corpora must be downloaded to `data/corpora/raw/` before running:
```bash
python -m src.data.download wisesight wongnai prachathai
```

## Configuration

- **Top-K words:** Default 500, adjustable via `--top-k` in Steps 1 and 2
- **Max variants per word:** Default 20, adjustable via `--max-variants` in Step 2
- **Corpus weighting:** Equal (1/3 each), hardcoded in Step 1
- **Target benchmark size:** ~300 approved entries after manual review

## Output Files

All intermediate outputs are in `pipelines/benchmark-wordconv/output/` (gitignored). The final benchmark CSV goes to `benchmarks/word-conversion/basic.csv`.
