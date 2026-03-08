# Experiments — pipeline/variant-generator-v2

Experiment artifacts for Change Plan 04 (Variant Generator v2 & Benchmark v0.2.0).
These files are tracked on the `pipeline/variant-generator-v2` branch only and
are not merged to `main`.

## Files

### Commit 3: v0.1.1 Benchmark Validation

- **`validate_v011.py`** — Runs the v2 generator against the v0.1.1 benchmark
  and measures reproduction rate. Used to iterate on dictionary entries.
- **`v011_validation_results.csv`** — Output from the validation script.
  Final reproduction rate: 93.3% raw, ~98% adjusted (excluding known-skips).

### Commit 4: Spot Checks During Review

- **`spot_check_top50.py`** — Quick script to generate and display variants
  for the top 50 words by frequency. Used for fast visual inspection.
- **`top50_variants.csv`** — Output from the spot check script.

### Commit 5: 10K Scale-Up Validation

- **`test_tltk_multiprocessing.py`** — Verifies TLTK produces identical
  results in forked child processes vs the main process. Confirmed PASS;
  gates the multiprocessing optimization in `02_generate_romanizations.py`.
- **`stratified_sample_10k.py`** — Samples ~300 words from the 10K draft
  benchmark, stratified by frequency tier, syllable count, and variant
  diversity. Also reports component dictionary coverage statistics.
- **`10k_stratified_sample.csv`** — The stratified sample with maintainer
  review annotations. 276/300 OK pre-fix; all 24 NOISE entries resolved
  by removing `d` from ต onset in dictionary v0.3.0.
