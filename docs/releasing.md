# Releasing

How to build and publish a THAIME NLP data release.

## Prerequisites

- On the `main` branch with a clean working tree
- All pipelines runnable (corpora downloaded, dependencies installed)
- `gh` CLI authenticated with push/release permissions

## Build a Release

```bash
# Full build: runs trie + ngram pipelines, smoke test, then stages artifacts
python scripts/build-release.py v0.1.0

# Skip pipeline rebuild (use cached outputs from a previous run)
python scripts/build-release.py v0.1.0 --skip-pipelines

# Skip smoke test only
python scripts/build-release.py v0.1.0 --skip-smoke-test
```

The script:

1. Validates the version format (`vMAJOR.MINOR.PATCH`) and working tree state
2. Runs `python -m pipelines trie run --release-version {version}` and `python -m pipelines ngram run`
3. Runs `python -m pipelines smoke-test` to validate artifacts
4. Compresses each artifact with gzip
5. Generates SHA-256 checksums (`sha256sums.txt`)
6. Compares checksums against the previous GitHub release (detects stale builds)
7. Resolves input data versions (overrides, exclusions, component romanization, benchmark)
8. Generates `manifest.json` with full provenance metadata
9. Stages everything into `pipelines/outputs/release/`
10. Prints a ready-to-use `gh release create` command

## Review Before Publishing

Check the build summary output for:

- **Warnings** — uncommitted changes, skipped steps, wrong branch
- **Hash comparison** — `UNCHANGED` artifacts may indicate a stale rebuild
- **Smoke test** — all cases should pass (failures block the build)
- **Manifest** — verify input data versions match expectations

```bash
# Inspect staged artifacts
ls -la pipelines/outputs/release/
cat pipelines/outputs/release/manifest.json
```

## Publish

Copy the `gh release create` command printed by the build script. It includes:

- Release title and version tag
- Release body with artifact table, input versions, checksums
- All compressed artifacts and the manifest as upload assets

```bash
# Example (the script prints the actual command with correct paths):
gh release create v0.1.0 \
    --title "THAIME NLP v0.1.0" \
    --notes "..." \
    "pipelines/outputs/release/trie_dataset.json.gz" \
    "pipelines/outputs/release/thaime_ngram_v1_mc15.bin.gz" \
    ...
```

## Artifact Inventory

| File | Description |
|---|---|
| `trie_dataset.json.gz` | Trie dictionary dataset — word entries with romanization keys and frequencies |
| `thaime_ngram_v1_mc15.bin.gz` | Pre-scored n-gram binary for the Viterbi language model (see [handover spec](handover-ngram-binary-v1.md)) |
| `ngrams_1_merged_raw.tsv.gz` | Raw unigram counts (diagnostic / research use) |
| `ngrams_2_merged_raw.tsv.gz` | Raw bigram counts (diagnostic / research use) |
| `ngrams_3_merged_raw.tsv.gz` | Raw trigram counts (diagnostic / research use) |
| `manifest.json` | Build provenance: version, commit, timestamp, input versions, checksums |
| `sha256sums.txt` | SHA-256 checksums for all compressed artifacts |

## How the Engine Consumes Releases

The main [thaime](https://github.com/mimocha/thaime) engine downloads release assets at build time:

1. `trie_dataset.json.gz` is decompressed and loaded into the prefix-search trie
2. `thaime_ngram_v1_mc15.bin.gz` is decompressed and memory-mapped for Viterbi scoring

See [handover-ngram-binary-v1.md](handover-ngram-binary-v1.md) for the binary format specification.

## Checksum Format in Release Notes

Checksums are embedded in the release body in a machine-parseable format:

```
sha256:<filename>:<hex_digest>
```

The build script reads these from the previous release to detect changed/unchanged artifacts. This avoids needing a separate checksum storage mechanism.
