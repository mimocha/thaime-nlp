# THAIME Data Generation Pipelines

Production data pipelines that generate artifacts consumed by the THAIME engine.

## Quick Start

```bash
# Full trie pipeline
python -m pipelines trie run

# Full n-gram pipeline
python -m pipelines ngram run

# Benchmark generation (automated steps)
python -m pipelines benchmark word-conversion run
```

Or use the installed script:

```bash
thaime-pipeline trie run
thaime-pipeline ngram run
```

## CLI Command Tree

```
python -m pipelines [--no-cache] [--workers N]
├── trie
│   ├── run              # Full: wordlist -> variant -> filter -> export
│   ├── wordlist         # Step 1 only
│   ├── variant          # Step 2 only
│   ├── export           # Steps 3-4 only
│   ├── review           # Read-only inspection
│   └── validate         # Benchmark regression
├── ngram
│   ├── run              # Full: tokenize -> count -> validate
│   ├── tokenize         # Stage 1 only
│   ├── count            # Stage 2 only
│   └── validate         # Stage 3 only
└── benchmark
    └── word-conversion
        ├── run           # Full: extract -> romanize
        ├── extract       # Step 1: word frequencies
        ├── romanize      # Step 2: generate romanizations
        ├── review        # Step 3: interactive review
        └── export        # Step 4: CSV export
```

## Output Structure

All pipeline outputs go to `pipelines/outputs/` (gitignored):

```
pipelines/outputs/
├── tokens/              # Tokenized corpus files (shared)
│   ├── tokens_wisesight.txt
│   ├── tokens_wongnai.txt
│   ├── tokens_prachathai.txt
│   └── tokens_thwiki.txt
├── wordlist/            # Word frequency tables
│   └── wordlist.csv
├── variants/            # Variant generation results
│   ├── variants.json
│   └── variant_strategies.log
├── trie/                # Final trie artifacts
│   ├── trie_dataset.json
│   ├── trie_dataset.csv
│   └── benchmark_missed.csv
├── ngram/               # Final n-gram artifacts
│   ├── ngrams_{1,2,3}_merged.tsv
│   ├── ngrams_{1,2,3}_merged_raw.tsv
│   └── ngrams_{1,2,3}_{corpus}.tsv
└── benchmarks/
    └── word_conversion/
        ├── word_frequencies.csv
        ├── draft_benchmark.json
        └── reviewed_benchmark.json
```

## Shared Code

Pipelines import shared modules from `src/`:

- `src/corpora/` — corpus reading, tokenization, validation
- `src/utils/frequency.py` — frequency normalization and merging
- `src/utils/versioning.py` — semantic version file resolution
- `src/variant_generator.py` — romanization variant generation

## Global Options

- `--no-cache` — ignore cached intermediate files, force full rebuild
- `--workers N` — override worker count for all sub-pipelines

## Caching

By default, pipelines reuse existing intermediate files. Use `--no-cache` to force regeneration. There is no hash-based staleness detection — manage manually.

## Dependencies

All dependencies are in `pyproject.toml`. Key libraries:
- PyThaiNLP (tokenization)
- TLTK (romanization, g2p)
- Click (CLI framework)
- Rich (console output, progress bars)
