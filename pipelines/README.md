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
│   ├── run              # Full: tokenize -> count -> validate -> encode
│   ├── tokenize         # Stage 1 only
│   ├── count            # Stage 2 only
│   ├── validate         # Stage 3 only
│   └── encode           # Stage 4: binary encoding
├── llm-filter
│   ├── generate         # Run LLM filter on wordlist → raw exclusion candidates
│   └── approve          # Copy reviewed exclusion list to data directory
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
│   ├── ngrams_{1,2,3}_{corpus}.tsv
│   └── thaime_ngram_v1_mc{N}.bin  # Production binary
├── llm_filter/          # LLM filter outputs
│   ├── dropped_words_raw.txt
│   └── llm_filter.log
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

## Word Validation & Filtering

Both the trie and n-gram pipelines share a multi-layer filtering system that decides which tokens from the corpus become vocabulary entries. Understanding these layers is important because a word rejected at any layer is excluded from **all** pipeline outputs — trie dataset, frequency counts, and n-gram tables.

### Layer 1: Structural validation (`src/corpora/validation.py`)

`is_valid_thai_word()` is a fast, regex-based gate applied during tokenization. It runs on every token from every corpus source and rejects obvious non-words before any expensive processing. Both pipelines call it via `src/corpora/tokenizer.py`.

Current rules (applied in order, cheapest first):

| # | Rule | Rejects | Examples |
|---|------|---------|----------|
| 1 | Length bounds | Empty, single-char, and >30-char tokens | `ก`, `""` |
| 2 | Thai-script-only | Tokens with digits, Latin, punctuation | `hello`, `123`, `ก.` |
| 3 | Maiyamok-only | Pure ๆ repetition sequences | `ๆๆๆ` |
| 4 | Leading maiyamok | Tokenizer fragments starting with ๆ | `ๆคน` (from `จริงๆคน`) |
| 5 | Repeated chars (4+) | Spam / internet slang | `ดดดด`, `กกกก` |
| 6 | No-consonant tokens | Pure vowel/mark sequences | `าาา`, `ะะ`, `็็` |
| 7 | Single repeating char | Same character repeated | `ดดด`, `กกก` |

**Design principle:** These rules are intentionally conservative structural checks. Semantic filtering (is this a real Thai word?) is handled by later layers. Legitimate words that happen to match a structural pattern are rescued via word overrides (see Layer 4).

### Layer 2: Word exclusion list (`data/dictionaries/word_exclusions/`)

A curated list of tokens to reject, maintained as a plain text file. Applied after tokenization in the trie pipeline's export stage. Override words are exempt from exclusion.

The exclusion list is generated by the LLM filter (see below) and reviewed by the maintainer before being committed.

### Layer 3: LLM semantic filter (`pipelines/llm_filter/`)

An offline tool (not part of the automated pipeline) that uses AWS Bedrock to semantically evaluate whether tokens are real Thai words. Produces candidate exclusions that the maintainer reviews and merges into the exclusion list. Invoked via `python -m pipelines llm-filter generate`.

The LLM filter skips the top N words by frequency (`RAW_WORDLIST_LIMIT`, default 5000) on the assumption that high-frequency tokens are legitimate.

### Layer 4: Word overrides (`data/dictionaries/word_overrides/`)

Manual override entries that bypass all filtering. Used for two cases:
1. **TLTK failures** — words that TLTK cannot romanize (the override provides explicit romanizations)
2. **Filter false positives** — legitimate words caught by structural rules (e.g., `กก`, `งง`)

Override words are exempt from the exclusion list and dataset quality filters (source count, frequency threshold). They receive a floor frequency equal to the minimum observed corpus frequency, so they remain selectable by Viterbi scoring.

### Layer 5: Dataset quality filters (`pipelines/trie/generate.py`)

Applied after variant generation in the trie pipeline's export stage. These filter on data quality rather than token structure:

| # | Filter | Threshold | Override-exempt? |
|---|--------|-----------|-----------------|
| 1 | Source count | ≥ 2 sources (pythainlp-only exempt) | Yes |
| 2 | Frequency | ≥ configured minimum | Yes |
| 3 | Length ratio | Thai base length / min romanization length | Yes |
| 4 | Zero variants | Words with no romanization output | No |
| 5 | Vocabulary limit | Top N by frequency | Yes (always kept) |

### How layers interact

```
Corpus text
  → Tokenizer (PyThaiNLP / TLTK)
    → Layer 1: is_valid_thai_word() — structural rejection
      → Word counting & frequency normalization
        → Layer 4: Word overrides — add manual entries, assign floor frequency
          → Layer 2: Exclusion list — remove curated bad tokens
            → Variant generation (TLTK romanization + component dictionary)
              → Layer 5: Dataset quality filters
                → Final trie dataset
```

The n-gram pipeline shares Layer 1 (via the same tokenizer) and uses the final trie dataset as its vocabulary filter, so Layers 2–5 indirectly affect n-gram coverage.

## Dependencies

All dependencies are in `pyproject.toml`. Key libraries:
- PyThaiNLP (tokenization)
- TLTK (romanization, g2p)
- Click (CLI framework)
- Rich (console output, progress bars)
