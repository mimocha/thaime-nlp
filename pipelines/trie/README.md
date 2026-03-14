# Trie Generation Pipeline

Generates the trie-ready dataset for the THAIME engine: a mapping of romanization keys to Thai words, produced by assembling vocabulary from multiple Thai corpora and generating romanization variants via a dictionary-driven approach.

## Overview

The pipeline follows a 4-stage data flow:

```
Input Sources → Word List Assembly → Variant Generation → Filtering → Export
```

1. **Word list assembly** — Union vocabulary from 5 sources, deduplicate, compute merged frequencies.
2. **Variant generation** — Run the dictionary-driven variant generator (`src/variant_generator.py`) on each word via multiprocessing.
3. **Filtering** — Apply quality filters (source count, frequency, romanization sanity) to remove noise. Manual overrides bypass all filters.
4. **Export** — Output JSON + CSV dataset with statistics.

## Prerequisites

Corpora must be downloaded to `data/corpora/raw/` before running:

```bash
python -m src.data.download wisesight wongnai prachathai thwiki
```

PyThaiNLP's built-in word list is downloaded automatically on first use.

## Usage

```bash
# Full pipeline (all steps)
python -m pipelines trie run

# Individual steps (use cached intermediates)
python -m pipelines trie wordlist    # Step 1 only
python -m pipelines trie variant     # Step 2 only (requires wordlist.csv)
python -m pipelines trie export      # Steps 3-4 only (requires wordlist.csv + variants.json)

# Inspection and validation
python -m pipelines trie review      # Read-only dataset inspection
python -m pipelines trie validate    # Benchmark regression check
```

Caching: the pipeline saves intermediate files (`wordlist.csv`, `variants.json`) and reuses them on subsequent runs. Use `--no-cache` to force regeneration.

### Subcommands

#### `trie run`

Runs all pipeline steps in sequence.

```bash
python -m pipelines trie run
python -m pipelines trie run --sources wisesight,wongnai,pythainlp
python -m pipelines trie run --workers 4 --max-variants 50
python -m pipelines trie run --no-cache
```

| Option | Description |
|--------|-------------|
| `--sources` | Comma-separated source names (default: all five) |
| `--workers` | Parallel workers (default: 8, 0=sequential) |
| `--max-variants` | Max variants per word (default: 100) |
| `--vocab-limit` | Limit vocabulary size (default: unlimited) |
| `--min-sources` | Minimum source count (default: 2) |
| `--exclusion-list` / `--no-exclusion-list` | Toggle word exclusion list |
| `--overrides` | Path to overrides YAML (default: auto-resolve latest) |
| `--output-dir` | Custom output directory |
| `--no-cache` | Force full rebuild, ignore cached files |

#### `trie review`

Read-only inspection tool for spot-checking the generated dataset:

```bash
python -m pipelines trie review                           # Dataset summary
python -m pipelines trie review --source prachathai       # Words in prachathai
python -m pipelines trie review --source-only thwiki      # Words ONLY in thwiki
python -m pipelines trie review --failures                # 0-variant words
python -m pipelines trie review --collisions              # Key collisions
python -m pipelines trie review --search กาแฟ             # Search
```

## Data Sources

| Source | Category | Description |
|--------|----------|-------------|
| Wisesight | Informal | Social media sentiment corpus (26K messages) |
| Wongnai | Informal | Restaurant review corpus (247K reviews) |
| Prachathai | Formal | News article corpus (67K articles) |
| Thai Wikipedia | Encyclopedic | Thai Wikipedia XML dump (~500MB compressed) |
| PyThaiNLP | Dictionary | Curated built-in word list |

## Configuration

Parameters in `pipelines/config.py` (`TrieConfig` class):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_source_count` | 2 | Minimum corpus sources per word (pythainlp-only exempt) |
| `min_frequency` | 5e-6 | Minimum word frequency after normalization |
| `max_length_ratio` | 2.0 | Max `thai_base_len / min_rom_len` before removal |
| `max_variants_per_word` | 100 | Cap on romanization variants per word |
| `num_workers` | 8 | Parallel worker processes for variant generation |

## Output Files

All outputs are in `pipelines/outputs/` (gitignored):

| Path | Description |
|------|-------------|
| `wordlist/wordlist.csv` | Intermediate: assembled word list with frequencies |
| `variants/variants.json` | Intermediate: romanization variants per word |
| `trie/trie_dataset.json` | Final: structured dataset with metadata |
| `trie/trie_dataset.csv` | Final: flat format, one row per romanization key |

### Output format

**JSON** (`trie_dataset.json`):
```json
{
  "metadata": {
    "version": "0.1.0",
    "generated_at": "2026-03-10T...",
    "vocab_size": 17658,
    "total_romanization_keys": 568428,
    "unique_romanization_keys": 535585,
    "sources": ["prachathai", "pythainlp", "thwiki", "wisesight", "wongnai"]
  },
  "entries": [
    {
      "word_id": 0,
      "thai": "ที่",
      "frequency": 0.0182,
      "sources": ["prachathai", "pythainlp", "thwiki", "wisesight", "wongnai"],
      "romanizations": ["thi", "thee", "ti", "tee"]
    }
  ]
}
```

## Known Limitations

- **Loanword romanization** — Words like กาแฟ→"coffee" are not systematically handled.
- **Equal variant weights** — All romanization variants are treated equally.
- **TLTK dependency** — Variant generation requires TLTK, which is only available in the devcontainer environment.
