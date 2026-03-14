# N-gram Generation Pipeline

Tokenizes Thai corpora and extracts n-gram frequency data (unigrams, bigrams, trigrams) for use by the THAIME engine's language model.

Based on findings from [Research 007: Bigram Scoring](../../research/007-bigram-scoring/summary.md).

## Prerequisites

- **Trie dataset**: `pipelines/outputs/trie/trie_dataset.json` (run the trie pipeline first)
- **Raw corpora**: Downloaded to `data/corpora/raw/` (wisesight, wongnai, prachathai, thwiki)
- **PyThaiNLP**: Available in the devcontainer environment

## Usage

```bash
# Full pipeline (tokenize → count → validate)
python -m pipelines ngram run

# With custom options
python -m pipelines ngram run --workers 4 --corpora wisesight,wongnai

# Individual stages (use cached intermediates)
python -m pipelines ngram tokenize    # Stage 1 only
python -m pipelines ngram count       # Stage 2 only
python -m pipelines ngram validate    # Stage 3 only
```

Caching: the pipeline saves intermediate token files and reuses them on subsequent runs. Use `--no-cache` to force re-tokenization.

### Subcommands

#### `ngram run`

Runs all three stages in sequence.

```bash
python -m pipelines ngram run
python -m pipelines ngram run --corpora wisesight,wongnai --workers 4
python -m pipelines ngram run --no-cache
```

| Option | Description |
|--------|-------------|
| `--corpora` | Comma-separated corpus names (default: all four) |
| `--workers` | Worker processes (default: 8, 0=sequential) |
| `--vocab-filter` | Path to trie dataset JSON for vocabulary filtering |
| `--no-vocab-filter` | Disable vocabulary filtering |
| `--min-count` | Minimum n-gram count for raw TSVs (default: 2) |
| `--no-cache` | Force re-tokenization even if token files exist |

#### `ngram tokenize`

Stage 1: Tokenize corpora into cached token files.

| Option | Description |
|--------|-------------|
| `--corpora` | Comma-separated corpus names (default: all four) |
| `--workers` | Worker processes (default: 8, 0=sequential) |
| `--vocab-filter` | Path to trie dataset JSON for vocabulary filtering |
| `--no-vocab-filter` | Disable vocabulary filtering |

#### `ngram count`

Stage 2: Count n-grams from cached token files.

| Option | Description |
|--------|-------------|
| `--corpora` | Comma-separated corpus names (default: all four) |
| `--min-count` | Minimum n-gram count in output (default: 2) |

#### `ngram validate`

Stage 3: Validate n-gram coverage against the ranking benchmark.

## Output Files

All outputs are in `pipelines/outputs/` (gitignored):

| Path | Description |
|------|-------------|
| `tokens/tokens_{corpus}.txt` | Intermediate: one token per line, blank lines = boundaries |
| `ngram/ngrams_{n}_{corpus}.tsv` | Per-corpus raw counts (min_count filtered) |
| `ngram/ngrams_{n}_merged_raw.tsv` | Sum of counts across corpora |
| `ngram/ngrams_{n}_merged.tsv` | Equal-weight normalized merge (scientific notation) |

The normalized merge (`_merged.tsv`) is the primary output — each corpus is normalized to sum to 1.0, then all corpora contribute equally (weight = 1/N).

### Token File Format

- One token per line
- Blank lines indicate sequence boundaries (document boundaries, or positions where non-Thai tokens were removed)

### N-gram TSV Format

Tab-separated: `token1\ttoken2\t...\tcount_or_frequency`

## Data Quality: Sequence Boundary Fix

The tokenization stage inserts sequence boundaries where non-Thai tokens (numbers, English text, punctuation) are removed. This prevents false n-gram adjacencies:

```
Original:  ราคา 500 บาท
Without fix: [ราคา, บาท]     → false bigram (ราคา, บาท)
With fix:    [ราคา, ∅, บาท]  → no bigram across boundary
```

## Known Limitations

- Sequence boundaries are the only special token; no sentence-start/end markers
- Vocabulary filtering depends on the trie dataset — words not in the trie are treated as boundaries
- The Wikipedia corpus may contain residual markup noise despite cleanup
