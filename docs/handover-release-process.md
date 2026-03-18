# THAIME NLP Release Process — Handover

How the thaime-nlp repository builds, versions, and publishes data artifacts consumed by the thaime engine.

## Overview

The thaime-nlp repo produces two primary data files that the engine loads at runtime:

1. **Trie dataset** (`trie_dataset.json.gz`) — dictionary of Thai words with romanization keys and frequencies, used for prefix-search trie construction
2. **N-gram binary** (`thaime_ngram_v1_mc15.bin.gz`) — pre-scored language model for Viterbi candidate ranking (see [handover-ngram-binary-v1.md](handover-ngram-binary-v1.md) for the binary format spec)

Both are published as GitHub release assets on the [thaime-nlp](https://github.com/mimocha/thaime-nlp) repository.

## Release Artifacts

Each release contains:

| File | Format | Engine use |
|---|---|---|
| `trie_dataset.json.gz` | gzip'd JSON | Decompress → load into prefix-search trie |
| `thaime_ngram_v1_mc15.bin.gz` | gzip'd binary | Decompress → memory-map or read for Viterbi scoring |
| `ngrams_1_merged_raw.tsv.gz` | gzip'd TSV | Not used by engine (diagnostic/research data) |
| `ngrams_2_merged_raw.tsv.gz` | gzip'd TSV | Not used by engine (diagnostic/research data) |
| `ngrams_3_merged_raw.tsv.gz` | gzip'd TSV | Not used by engine (diagnostic/research data) |
| `manifest.json` | JSON | Build provenance (version, commit, input versions, checksums) |

The engine only needs `trie_dataset.json.gz` and `thaime_ngram_v1_mc15.bin.gz`.

## Versioning

Releases follow semantic versioning: `v{MAJOR}.{MINOR}.{PATCH}`.

- **MAJOR** — breaking format changes (trie JSON schema change, n-gram binary format bump)
- **MINOR** — new data (added words, retrained n-grams, new corpora)
- **PATCH** — fixes (exclusion list updates, romanization corrections)

The trie dataset JSON includes the release version in its `metadata.version` field. The n-gram binary encodes build info in its header (see [handover-ngram-binary-v1.md](handover-ngram-binary-v1.md)).

## Trie Dataset Format

The trie JSON has this structure:

```json
{
  "metadata": {
    "version": "v0.1.0",
    "generated_at": "2026-03-19T12:00:00+00:00",
    "vocab_size": 12345,
    "total_romanization_keys": 67890,
    "unique_romanization_keys": 54321,
    "sources": ["wisesight", "wongnai", "prachathai", "thwiki", "pythainlp"]
  },
  "entries": [
    {
      "word_id": 0,
      "thai": "มา",
      "frequency": 0.001234,
      "romanizations": ["ma", "maa"],
      "sources": ["wisesight", "wongnai"]
    }
  ]
}
```

Each entry has:

| Field | Type | Description |
|---|---|---|
| `word_id` | int | Unique ID (0-indexed), matches n-gram binary word IDs |
| `thai` | str | Thai word text |
| `frequency` | float | Normalized frequency from corpus data |
| `romanizations` | list[str] | All Latin keys that should match this word in prefix search |
| `sources` | list[str] | Which corpora contributed this word |

**Important:** `word_id` values in the trie dataset correspond 1:1 with the word IDs in the n-gram binary's string table. Both files must come from the same release.

## Manifest Format

Each release includes a `manifest.json` for build provenance:

```json
{
  "release": "v0.1.0",
  "commit": "abc1234def5678...",
  "timestamp": "2026-03-19T12:00:00+00:00",
  "inputs": {
    "overrides": "v0.5.0",
    "exclusions": "v0.5.0",
    "component_romanization": "v0.5.0",
    "benchmark_word_conversion": "v0.4.1"
  },
  "artifacts": {
    "trie_dataset.json.gz": {
      "sha256": "...",
      "size_bytes": 12345678,
      "uncompressed_size_bytes": 45678901
    }
  }
}
```

## Fetching Release Assets

### Using gh CLI (recommended for build scripts)

```bash
# Download the two engine-required assets from the latest release
gh release download --repo mimocha/thaime-nlp \
    --pattern "trie_dataset.json.gz" \
    --pattern "thaime_ngram_v1_mc15.bin.gz" \
    --dir data/

# Download from a specific version
gh release download v0.1.0 --repo mimocha/thaime-nlp \
    --pattern "trie_dataset.json.gz" \
    --pattern "thaime_ngram_v1_mc15.bin.gz" \
    --dir data/

# Get the latest release tag
gh release view --repo mimocha/thaime-nlp --json tagName -q .tagName
```

### Using the GitHub API directly

```
GET https://api.github.com/repos/mimocha/thaime-nlp/releases/latest
```

The response includes an `assets` array with `browser_download_url` for each file.

### Verifying downloads

Each release body contains checksums in parseable format:

```
sha256:<filename>:<hex_digest>
```

To verify:

```bash
# Extract checksums from release notes
gh release view --repo mimocha/thaime-nlp --json body -q .body | grep "^sha256:"

# Compare against downloaded files
sha256sum data/trie_dataset.json.gz
```

## Integration Notes

- The trie dataset and n-gram binary are **paired** — always use both from the same release. Mismatched files will produce incorrect word IDs in n-gram lookups.
- Both files are gzip-compressed. Decompress before use (`gunzip` or programmatic decompression).
- For WASM builds, consider re-compressing the n-gram binary with brotli for smaller transfer size (see size targets in [handover-ngram-binary-v1.md](handover-ngram-binary-v1.md)).
- The trie dataset JSON is ~15–20 MB uncompressed. Parse it at build time or startup; do not bundle the JSON at runtime if the engine uses a compiled trie structure.

## Release Links

<!-- TODO: Add links to releases, or use gh CLI to fetch latest -->
<!-- gh release view --repo mimocha/thaime-nlp --json tagName,url -->

| Version | Date | Notes |
|---|---|---|
| — | — | No releases published yet |
