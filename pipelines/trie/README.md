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
python -m pipelines.trie.generate

# Individual steps (use cached intermediates)
python -m pipelines.trie.generate --wordlist-only     # Step 1 only
python -m pipelines.trie.generate --variant-only      # Step 2 only (requires wordlist.csv)
python -m pipelines.trie.generate --export-only       # Steps 3-4 only (requires wordlist.csv + variants.json)

# Options
python -m pipelines.trie.generate --sources wisesight,wongnai,pythainlp  # Subset of sources
python -m pipelines.trie.generate --workers 4         # Parallel workers (default: 8, 0=sequential)
python -m pipelines.trie.generate --max-variants 50   # Max variants per word (default: 100)
python -m pipelines.trie.generate --no-cache          # Force full rebuild, ignore cached files
python -m pipelines.trie.generate --output-dir /path  # Custom output directory
```

Caching: the pipeline saves intermediate files (`wordlist.csv`, `variants.json`) and reuses them on subsequent runs. Use `--no-cache` to force regeneration.

## Review CLI

Read-only inspection tool for spot-checking the generated dataset:

```bash
# Dataset summary
python -m pipelines.trie.review

# Filter by source
python -m pipelines.trie.review --source prachathai        # Words in prachathai
python -m pipelines.trie.review --source-only thwiki       # Words ONLY in thwiki
python -m pipelines.trie.review --source-min 3             # Words in 3+ sources

# Filter by variants
python -m pipelines.trie.review --failures                 # 0-variant words
python -m pipelines.trie.review --min-variants 50          # High-variant words
python -m pipelines.trie.review --max-variants 2           # Low-variant words

# Collisions
python -m pipelines.trie.review --collisions               # Keys mapping to 2+ words
python -m pipelines.trie.review --collisions --min-collision 10  # High-collision keys

# Search and export
python -m pipelines.trie.review --search กาแฟ              # Search Thai words or keys
python -m pipelines.trie.review --source-min 5 --export high_confidence.csv
```

## Data Sources

| Source | Category | Description |
|--------|----------|-------------|
| Wisesight | Informal | Social media sentiment corpus (26K messages) |
| Wongnai | Informal | Restaurant review corpus (247K reviews) |
| Prachathai | Formal | News article corpus (67K articles) |
| Thai Wikipedia | Encyclopedic | Thai Wikipedia XML dump (~500MB compressed) |
| PyThaiNLP | Dictionary | Curated built-in word list |

All corpora are tokenized with PyThaiNLP (`newmm` engine) and filtered for valid Thai tokens.

## Configuration

Parameters in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_SOURCE_COUNT` | 2 | Minimum corpus sources per word (pythainlp-only exempt) |
| `MIN_FREQUENCY` | 5e-6 | Minimum word frequency after normalization |
| `MAX_LENGTH_RATIO` | 2.0 | Max `thai_base_len / min_rom_len` before removal |
| `MAX_VARIANTS_PER_WORD` | 100 | Cap on romanization variants per word |
| `NUM_WORKERS` | 8 | Parallel worker processes for variant generation |

## Manual Overrides

`overrides.yaml` contains manually curated romanizations for words the variant generator can't handle correctly:

- TLTK failures (colloquial particles, slang)
- Words filtered by aggressive regex rules but still valid
- Loanwords with English-style romanizations (e.g., เรนเจอร์ → ranger)
- False positives from the length-ratio filter (e.g., เหมาะ, เอ็กซ์)

Override words bypass all dataset filters. Currently 240 entries.

## Output Files

All outputs are in `pipelines/trie/outputs/` (gitignored). Re-run the pipeline to regenerate.

| File | Description |
|------|-------------|
| `wordlist.csv` | Intermediate: assembled word list with frequencies and sources |
| `variants.json` | Intermediate: romanization variants per word (large, ~500MB) |
| `trie_dataset.json` | Final: structured dataset with metadata and all entries |
| `trie_dataset.csv` | Final: flat format, one row per romanization key |
| `variant_strategies.log` | Log of non-standard variant generation strategies used |

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

**CSV** (`trie_dataset.csv`):
```
word_id,thai,romanization_key,frequency,sources
0,ที่,thi,0.0182,prachathai|pythainlp|thwiki|wisesight|wongnai
0,ที่,thee,0.0182,prachathai|pythainlp|thwiki|wisesight|wongnai
```

## Validation

`validate.py` checks the dataset against the word-conversion benchmark:

```bash
python -m pipelines.trie.validate
```

Reports benchmark recall, per-source coverage, and collision statistics.

## Known Limitations

- **Loanword romanization** — Words like กาแฟ→"coffee" are not systematically handled. A separate loanword pipeline is planned (`pipeline/trie-loanwords`).
- **Equal variant weights** — All romanization variants are treated equally. Future work could assign weights based on typing probability.
- **Frequency bias** — Equal-weight averaging across sources means corpus-specific frequency patterns (e.g., ร้าน dominant in Wongnai) are diluted.
- **TLTK dependency** — Variant generation requires TLTK, which is only available in the devcontainer environment.
