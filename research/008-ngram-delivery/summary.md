# N-gram Data Delivery Format

**Date:** 2026-03-18
**Author:** THAIME Research (agent + maintainer)
**Branch:** research/008-ngram-delivery
**Status:** Complete

## Research Question

What compact binary format should THAIME use to deliver n-gram data (unigrams, bigrams, trigrams) for both native Linux IME and WASM web demo deployment, within a brotli-compressed budget of ≤ 10 MB?

## Approach

Surveyed 7 candidate binary encodings spanning flat arrays, quantized log-probabilities, minimal perfect hashing, FST maps, and Elias-Fano tries. Implemented Python encoders for each and measured raw size, gzip-compressed size, and brotli-compressed size across 5 min_count thresholds (2, 5, 10, 25, 50). For quantized formats, measured error distribution and rank preservation over 10K random pairs. Three formats (E4 MPH, E6 FST, E7 EF trie) were size simulations only — their production implementations would use dedicated Rust crates.

Source data: 15,876 unigrams, 2,617,474 bigrams, 6,411,893 trigrams from the n-gram pipeline (4 corpora, ~107M tokens). Vocabulary is ~16K Thai words (fits in u16).

## Key Findings

### min_count is the dominant size lever

The single biggest factor in compressed size is the n-gram count threshold, not the encoding format. E1/E2 brotli sizes across thresholds:

| min_count | bi+tri entries | E1/E2 brotli |
|-----------|---------------|--------------|
| 2 | 9,029,367 | 31.78 MB |
| 5 | 3,072,163 | 11.72 MB |
| **10** | **1,544,971** | **6.18 MB** |
| **25** | **643,334** | **2.75 MB** |
| 50 | 329,161 | 1.49 MB |

Going from mc=2 to mc=10 reduces size by 5.1× (31.78 → 6.18 MB). Switching encoding at the same min_count yields at most 1.3× improvement.

### E1/E2 (flat sorted arrays) meets the hard constraint at mc ≥ 10

At mc=10: **6.18 MB brotli** — well within the 10 MB hard constraint. At mc=25: **2.75 MB** — meets the 5 MB soft target. Round-trip correctness verified: all 1,560,847 entries match exactly.

### Quantization is not worthwhile

- **u8/log fails** rank preservation: 87.08% (threshold: ≥ 99%).
- **u8/uniform** barely passes at 99.35%, with non-trivial mean error (0.018).
- **u16 variants** pass rank preservation but save negligible space after brotli: E3b_u16_log = 6.12 MB vs. E1/E2 = 6.18 MB at mc=10.
- All quantized formats lose raw counts, preventing runtime alpha tuning.

### Simulation caveats for E4 and E7

- **E4 (MPH):** Simulation stores values in sorted (TSV input) order rather than hash-function order. This makes brotli compression artificially optimistic. The reported 566 KB at mc=10 is unreliable; the raw size (6.70 MB) is the valid metric.
- **E7 (EF trie):** Simulation fills EF-sized buffers with random bytes, making brotli compression artificially pessimistic. The raw size (5.43 MB at mc=10) is accurate; real brotli would be better than the reported 5.17 MB.
- **E6 (FST):** Shared-prefix simulation is a reasonable approximation; 4.77 MB brotli at mc=10 is the most reliable of the three simulated formats.

### Brotli outperforms gzip consistently

Brotli -9 saves 5–20% over gzip -9 on all binary formats tested. With universal browser support, brotli is the correct choice for WASM HTTP delivery.

## Recommendation

### For the THAIME production engine

1. **Format: E1/E2 (flat sorted arrays with u16 word IDs + u32 counts)**
   - Simplest Rust implementation — struct packing only, zero external crate dependencies.
   - Same binary file supports both HashMap loading (O(1) lookup for native IME) and binary search (O(log N), zero-copy mmap for WASM).
   - Preserves raw counts for runtime alpha parameter tuning in Stupid Backoff.
   - Sorted layout compresses well under brotli.

2. **Minimum count threshold: mc ≥ 10 (hard), mc = 25 recommended**
   - mc=10 → 6.18 MB brotli (passes hard constraint).
   - mc=25 → 2.75 MB brotli (meets soft target, leaves headroom).
   - Quality impact of different thresholds should be evaluated against the ranking benchmark (separate concern).

3. **Compression: brotli for WASM delivery, raw binary for native**
   - WASM: serve `.br` files via HTTP with `Content-Encoding: br`.
   - Native: embed raw binary via `include_bytes!` or load from disk; 13.69 MB raw at mc=10 is acceptable for native.

### Rust binary file layout (proposed)

```
[string_table: len-prefixed UTF-8 words, ID = array index]
[unigrams: u32[vocab_size] indexed by word ID]
[bigrams: (u16 w1, u16 w2, u32 count)[N_bi], sorted by (w1, w2)]
[trigrams: (u16 w1, u16 w2, u16 w3, u32 count)[N_tri], sorted by (w1, w2, w3)]
```

### If further size reduction is needed

If evaluation shows mc=10's 6.18 MB is still too large for WASM:

1. **Increase min_count** — simplest lever; mc=25 cuts size to 2.75 MB.
2. **E6 (FST via `fst` crate)** — 4.77 MB brotli at mc=10; adds one dependency but provides native prefix queries.
3. **E7 (EF trie via `tongrams-rs`)** — near-optimal space, purpose-built for n-grams; more complex but raw size of 5.43 MB at mc=10 (real brotli likely 3–4 MB).

## Limitations

- **No Rust query latency benchmarks.** Python encode/decode timings do not predict Rust performance. HashMap vs. binary search vs. FST vs. MPH query latency must be evaluated with Rust criterion benchmarks in the engine repo.
- **Two simulations are unreliable for compression.** E4 (MPH) brotli sizes are artificially low; E7 (EF trie) brotli sizes are artificially high. Only raw sizes are valid for these formats.
- **min_count quality impact not measured.** This research measured size only. The effect of pruning low-count n-grams on ranking accuracy (MRR) needs separate evaluation using the ranking benchmark.
- **No WASM-specific testing.** Async loading, decompression time in the browser, and memory overhead of different formats were not measured.

## References

- Experiment branch: `research/008-ngram-delivery`
- Research plan: `experiments/008-ngram-delivery/008-ngram-delivery.md` (on branch)
- Experimental results: `experiments/008-ngram-delivery/results.md` (on branch)
- KenLM: Heafield 2011, "KenLM: Faster and Smaller Language Model Queries"
- PtrHash: Pibiri 2025, "PtrHash: Minimal Perfect Hashing"
- Elias-Fano n-gram trie: Pibiri & Venturini 2017/2019, SIGIR / ACM TOIS
- Rust crates: `fst` (BurntSushi), `ptr_hash`, `tongrams-rs`
