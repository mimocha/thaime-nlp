# N-gram Delivery Format: Experimental Results

**Topic:** research/008-ngram-delivery
**Date:** 2026-03-18
**Author:** THAIME Research (agent + maintainer)
**Depends on:** 008-ngram-delivery.md (combined hypothesis + plan)

## Setup

- **Python version:** 3.13 (devcontainer)
- **Key dependencies:** `brotli`, `gzip` (stdlib), `struct` (stdlib)
- **Hardware:** 16-core devcontainer (experiments parallelized via `ProcessPoolExecutor`)
- **Data:** N-gram TSVs from `pipelines/outputs/ngram/` — 15,876 unigrams, 2,617,474 bigrams, 6,411,893 trigrams
- **Vocab:** 15,876 unique Thai words (fits in u16)

## Encoding Legend

| Code | Format | Keys | Values | Notes |
|------|--------|------|--------|-------|
| E1 | Flat sorted arrays → HashMap | u16 IDs | u32 counts | Same binary as E2 |
| E2 | Flat sorted arrays + binary search | u16 IDs | u32 counts | Same binary as E1 |
| E3a | Quantized log-probs, u8 | u16 IDs | u8 bucket index | 256 buckets |
| E3b | Quantized log-probs, u16 | u16 IDs | u16 bucket index | 65,536 buckets |
| E4 | Minimal perfect hash (simulated) | None (MPH) | u32 counts | ⚠ See simulation caveats |
| E5 | Baseline TSV | Strings | String counts | Current status quo |
| E6 | FST map (simulated) | Prefix-compressed | u32 counts | Shared-prefix delta encoding |
| E7 | Elias-Fano trie (simulated) | EF-compressed | EF-compressed | ⚠ See simulation caveats |

## Results

### 1. Size Benchmark Matrix

#### min_count = 2

Entries: **15,876** uni + **2,617,474** bi + **6,411,893** tri = **9,045,243** total

| Encoding | Raw | gzip -9 | brotli -9 | Enc (s) |
|----------|-----|---------|-----------|---------|
| E4_mph_sim ⚠ | 37.39 MB | 2.74 MB | 2.70 MB | 2.6 |
| E6_fst_sim | 66.91 MB | 24.40 MB | 23.05 MB | 32.7 |
| E3a_u8_log | 55.63 MB | 28.89 MB | 25.97 MB | 112.1 |
| E3a_u8_uniform | 55.63 MB | 31.52 MB | 28.04 MB | 107.2 |
| E7_ef_trie_sim ⚠ | 28.90 MB | 28.65 MB | 28.63 MB | 46.0 |
| E3b_u16_log | 64.32 MB | 33.42 MB | 30.71 MB | 110.5 |
| E3b_u16_uniform | 64.26 MB | 34.53 MB | 31.66 MB | 108.4 |
| E1/E2 | 81.48 MB | 32.28 MB | 31.78 MB | 22.0 |
| E5_tsv | 370.98 MB | 75.23 MB | 61.95 MB | 2.6 |

#### min_count = 5

Entries: **15,876** uni + **1,244,196** bi + **1,827,967** tri = **3,088,039** total

| Encoding | Raw | gzip -9 | brotli -9 | Enc (s) |
|----------|-----|---------|-----------|---------|
| E4_mph_sim ⚠ | 12.96 MB | 1.02 MB | 1016.1 KB | 1.6 |
| E6_fst_sim | 23.07 MB | 9.24 MB | 8.75 MB | 11.1 |
| E3a_u8_log | 18.49 MB | 10.01 MB | 8.97 MB | 36.8 |
| E7_ef_trie_sim ⚠ | 10.19 MB | 9.94 MB | 9.93 MB | 26.3 |
| E3a_u8_uniform | 18.48 MB | 11.57 MB | 10.22 MB | 35.4 |
| E3b_u16_log | 21.49 MB | 12.50 MB | 11.56 MB | 33.7 |
| E1/E2 | 27.29 MB | 11.91 MB | 11.72 MB | 7.6 |
| E3b_u16_uniform | 21.43 MB | 13.25 MB | 12.17 MB | 29.7 |
| E5_tsv | 120.23 MB | 24.71 MB | 20.45 MB | 1.5 |

#### min_count = 10

Entries: **15,876** uni + **735,831** bi + **809,140** tri = **1,560,847** total

| Encoding | Raw | gzip -9 | brotli -9 | Enc (s) | Correctness |
|----------|-----|---------|-----------|---------|-------------|
| E4_mph_sim ⚠ | 6.70 MB | 586.7 KB | 566.2 KB | 0.9 | — |
| E3a_u8_log | 9.26 MB | 5.13 MB | 4.59 MB | 16.0 | — |
| E6_fst_sim | 11.85 MB | 5.00 MB | 4.77 MB | 7.2 | — |
| E7_ef_trie_sim ⚠ | 5.43 MB | 5.18 MB | 5.17 MB | 14.9 | — |
| E3a_u8_uniform | 9.26 MB | 6.03 MB | 5.40 MB | 19.5 | — |
| E3b_u16_log | 10.82 MB | 6.63 MB | 6.12 MB | 13.2 | — |
| **E1/E2** | **13.69 MB** | **6.29 MB** | **6.18 MB** | **6.2** | **All 1,560,847 match** |
| E3b_u16_uniform | 10.75 MB | 7.10 MB | 6.49 MB | 15.9 | — |
| E5_tsv | 59.33 MB | 12.16 MB | 10.19 MB | 1.2 | — |

#### min_count = 25

Entries: **15,876** uni + **362,284** bi + **281,050** tri = **659,210** total

| Encoding | Raw | gzip -9 | brotli -9 | Enc (s) |
|----------|-----|---------|-----------|---------|
| E4_mph_sim ⚠ | 3.00 MB | 318.9 KB | 303.4 KB | 0.4 |
| E3a_u8_log | 3.95 MB | 2.22 MB | 2.01 MB | 7.4 |
| E6_fst_sim | 5.20 MB | 2.30 MB | 2.24 MB | 1.8 |
| E7_ef_trie_sim ⚠ | 2.57 MB | 2.31 MB | 2.30 MB | 7.9 |
| E3a_u8_uniform | 3.95 MB | 2.61 MB | 2.31 MB | 6.7 |
| E3b_u16_log | 4.65 MB | 2.97 MB | 2.72 MB | 5.9 |
| E1/E2 | 5.81 MB | 2.80 MB | 2.75 MB | 2.1 |
| E3b_u16_uniform | 4.58 MB | 3.17 MB | 2.87 MB | 5.2 |
| E5_tsv | 23.96 MB | 5.01 MB | 4.26 MB | 0.4 |

#### min_count = 50

Entries: **15,876** uni + **205,675** bi + **123,486** tri = **345,037** total

| Encoding | Raw | gzip -9 | brotli -9 | Enc (s) |
|----------|-----|---------|-----------|---------|
| E4_mph_sim ⚠ | 1.71 MB | 224.5 KB | 210.3 KB | 0.2 |
| E3a_u8_log | 2.15 MB | 1.20 MB | 1.08 MB | 2.1 |
| E3a_u8_uniform | 2.15 MB | 1.40 MB | 1.26 MB | 2.9 |
| E7_ef_trie_sim ⚠ | 1.54 MB | 1.28 MB | 1.27 MB | 5.1 |
| E6_fst_sim | 2.88 MB | 1.29 MB | 1.28 MB | 1.1 |
| E1/E2 | 3.11 MB | 1.54 MB | 1.49 MB | 1.0 |
| E3b_u16_log | 2.56 MB | 1.64 MB | 1.50 MB | 2.3 |
| E3b_u16_uniform | 2.48 MB | 1.72 MB | 1.55 MB | 2.7 |
| E5_tsv | 12.13 MB | 2.61 MB | 2.23 MB | 0.3 |

### 2. Brotli Size Comparison Across min_count

| Encoding | mc=2 | mc=5 | mc=10 | mc=25 | mc=50 |
|----------|------|------|-------|-------|-------|
| E1/E2 | 31.78 MB | 11.72 MB | 6.18 MB | 2.75 MB | 1.49 MB |
| E3a_u8_uniform | 28.04 MB | 10.22 MB | 5.40 MB | 2.31 MB | 1.26 MB |
| E3a_u8_log | 25.97 MB | 8.97 MB | 4.59 MB | 2.01 MB | 1.08 MB |
| E3b_u16_uniform | 31.66 MB | 12.17 MB | 6.49 MB | 2.87 MB | 1.55 MB |
| E3b_u16_log | 30.71 MB | 11.56 MB | 6.12 MB | 2.72 MB | 1.50 MB |
| E4_mph_sim ⚠ | 2.70 MB | ~1.0 MB | 566 KB | 303 KB | 210 KB |
| E5_tsv | 61.95 MB | 20.45 MB | 10.19 MB | 4.26 MB | 2.23 MB |
| E6_fst_sim | 23.05 MB | 8.75 MB | 4.77 MB | 2.24 MB | 1.28 MB |
| E7_ef_trie_sim ⚠ | 28.63 MB | 9.93 MB | 5.17 MB | 2.30 MB | 1.27 MB |

### 3. Hard Constraint Check: brotli ≤ 10 MB

Excluding E4 (simulation unreliable — see caveats below).

| min_count | Formats passing hard constraint (≤ 10 MB) | E1/E2 size |
|-----------|-------------------------------------------|------------|
| **2** | None of the reliable formats | 31.78 MB |
| **5** | E6 (8.75), E3a/log (8.97), E7 (9.93) | 11.72 MB |
| **10** | **All binary formats pass** | **6.18 MB** |
| **25** | All formats including TSV baseline (4.26) | 2.75 MB |
| **50** | All formats | 1.49 MB |

**min_count ≥ 10 is the practical threshold** where E1/E2 comfortably meets the hard constraint.

### 4. Soft Target Check: brotli < 5 MB

At mc=10, excluding E4:

| Encoding | brotli -9 | Meets soft target? |
|----------|-----------|-------------------|
| E3a_u8_log | 4.59 MB | ✅ |
| E6_fst_sim | 4.77 MB | ✅ |
| E7_ef_trie_sim ⚠ | 5.17 MB | ❌ (but see caveat) |
| E3a_u8_uniform | 5.40 MB | ❌ |
| E3b_u16_log | 6.12 MB | ❌ |
| E1/E2 | 6.18 MB | ❌ |
| E3b_u16_uniform | 6.49 MB | ❌ |

At mc=25, all binary formats are under 3 MB.

### 5. Quantization Error Analysis (min_count = 10)

| Precision | Method | Mean Error | P95 Error | Max Error | Rank Preservation |
|-----------|--------|------------|-----------|-----------|-------------------|
| u8 (256) | uniform | 0.0176 | 0.0335 | 0.0353 | 99.35% |
| **u8 (256)** | **log** | **0.3105** | **0.6495** | **0.9153** | **87.08% ❌** |
| u16 (65536) | uniform | 0.0001 | 0.0001 | 0.0001 | **100.00%** |
| u16 (65536) | log | 0.0012 | 0.0026 | 0.0060 | 99.96% |

Success threshold: rank preservation ≥ 99%.

- **u8/log FAILS** with only 87.08% rank preservation — disqualified.
- **u8/uniform** barely passes at 99.35%, but mean error is higher than u16 variants.
- **u16/uniform** achieves perfect rank preservation with negligible error.
- **u16/log** is near-perfect at 99.96%.

### 6. Round-Trip Correctness

Full round-trip verification was performed for E1/E2 at mc=10: all 1,560,847 n-gram entries decoded back to their exact original counts. This confirms the encoding/decoding logic is correct.

Other non-quantized formats (E4, E6, E7) were simulations measuring size only — no decoder was implemented since the production implementation will use native Rust crates (`ptr_hash`, `fst`, `tongrams-rs`).

## Critical Observations

### Simulation Caveats

Two simulated formats have known biases that make their brotli numbers unreliable:

**⚠ E4 (MPH): Brotli sizes are artificially LOW**

The simulation stores values (u32 counts) in the original TSV input order, which is sorted by count descending. In a real MPH, values are stored at positions determined by the hash function — effectively a random permutation. Monotonically decreasing sequences compress dramatically better under brotli than randomly permuted sequences. The hash overhead bytes (`os.urandom`) correctly simulate incompressible hash-function data, but the value array's compression is far too optimistic.

At mc=10, the simulation reports 566 KB brotli. The real figure with randomly-permuted values would be significantly higher. The raw size (6.70 MB) is accurate: ~5.9 MB for u32 values + ~0.46 MB for 2.4 bits/key hash overhead + string table.

**Conclusion:** E4's compressed size cannot be compared directly with other formats. The raw size is valid, and E4 remains a viable candidate, but its compressed-size advantage in this experiment is an artifact.

**⚠ E7 (EF trie): Brotli sizes are artificially HIGH**

The simulation fills the EF-sized buffer with `os.urandom()` bytes, which are maximally incompressible. Real Elias-Fano bitvectors have structure: the high-bits portion is unary-coded (many `10` patterns), and the low-bits portion has bounded entropy. The raw size estimate is accurate (computed from the EF bit formula), but the brotli/gzip numbers are pessimistic upper bounds.

At mc=10: raw = 5.43 MB, brotli = 5.17 MB (only 5% compression). A real EF implementation would compress substantially better — likely in the 3–4 MB range based on published compression ratios for EF data.

**Conclusion:** E7's raw size is the meaningful metric from this simulation. Real brotli sizes would be lower, potentially competitive with E3a/E6.

### E6 (FST) Simulation Quality

The FST simulation uses shared-prefix delta encoding (storing shared prefix length + unique suffix per entry), which is a reasonable approximation of FST prefix sharing. However, a real FST also shares suffixes across branches and uses more sophisticated state merging. The simulation likely slightly overestimates size, but the numbers are much more reliable than E4 or E7.

### Brotli vs. gzip

Brotli -9 consistently outperforms gzip -9 by 5–20% on structured binary data. The advantage is smaller on already-compact formats (E7 random bytes: essentially zero improvement) and larger on redundant formats (E5 TSV: 75.23 → 61.95 MB at mc=2). For HTTP delivery (WASM target), brotli is universally supported and should be the compression method.

### min_count as the Primary Size Lever

The single biggest factor in compressed size is `min_count`, not encoding format. Going from mc=2 to mc=10 reduces E1/E2 brotli size by **5.1×** (31.78 → 6.18 MB), while the difference between E1/E2 and the best reliable alternative (E3a_u8_log) at the same mc=10 is only 1.3× (6.18 → 4.59 MB). The quality impact of different min_count thresholds on ranking accuracy is a separate concern to be evaluated with the ranking benchmark (Research 007).

### E3b (u16 quantization) Offers Negligible Benefit

E3b_u16 reduces values from 4 bytes to 2 bytes, but the compressed size savings over E1/E2 are marginal: 6.12 MB vs. 6.18 MB at mc=10 for the log variant. Brotli already exploits the low entropy of small count values in E1/E2, so reducing value precision yields little additional compression. E3b also loses raw counts, removing the ability to tune alpha at runtime.

## Synthesis & Recommendation

### Primary recommendation: E1/E2 (flat sorted arrays) at min_count ≥ 10

**E1/E2 is the clear winner for initial production deployment:**

- **6.18 MB brotli at mc=10** — well within the 10 MB hard constraint
- **2.75 MB brotli at mc=25** — meets the soft target with room to spare
- **Simplest implementation** — just struct packing, zero external crate dependencies in Rust
- **100% round-trip correctness** — verified on 1.56M entries
- **Preserves raw counts** — enables runtime `alpha` parameter tuning for Stupid Backoff
- **Dual runtime strategy** — same binary file supports both HashMap (O(1) lookup, higher memory) and binary search (O(log N), zero-copy mmap) without re-encoding
- **Sorted layout compresses well** — brotli can exploit the locality in sorted u16 IDs

E1 (HashMap at load time) is preferred for the native Linux IME where startup time is amortized. E2 (binary search / mmap) may be preferred for WASM where memory is constrained.

### Formats worth evaluating in Rust (but not critical)

If E1/E2's 6.18 MB at mc=10 proves insufficient (e.g., the WASM demo needs < 5 MB), these are the follow-up candidates:

1. **E6 (FST via `fst` crate):** 4.77 MB brotli at mc=10 in simulation (likely slightly better in practice). Battle-tested Rust crate, native prefix queries, WASM-compatible. Adds one crate dependency.

2. **E7 (EF trie via `tongrams-rs`):** Raw size of 5.43 MB at mc=10, with real brotli likely in the 3–4 MB range. Purpose-built for n-gram storage. More complex but near-optimal space.

3. **E4 (MPH via `ptr_hash`):** Raw size 6.70 MB at mc=10 — comparable to E1/E2's 13.69 MB raw, but compressed sizes are unknown (simulation unreliable). O(1) lookup, but no prefix queries and requires computing hash at query time. Worth a quick Rust benchmark if size pressure exists.

### Formats NOT recommended

- **E3a (u8 quantization):** u8/log fails rank preservation (87%) and u8/uniform barely passes (99.35%). Saves ~1.6 MB brotli over E1/E2 at mc=10 — not worth losing raw counts and scoring fidelity.
- **E3b (u16 quantization):** Negligible size benefit over E1/E2 after brotli (6.12 vs. 6.18 MB). Loses raw counts for no meaningful gain.
- **E5 (TSV baseline):** 10.19 MB at mc=10 exceeds the hard constraint. Not viable for production.

### min_count Guidance

| min_count | bi+tri entries | E1/E2 brotli | Constraint status |
|-----------|---------------|--------------|-------------------|
| 2 | 9,029,367 | 31.78 MB | ❌ Hard fail |
| 5 | 3,072,163 | 11.72 MB | ❌ Hard fail |
| **10** | **1,544,971** | **6.18 MB** | **✅ Hard pass** |
| **25** | **643,334** | **2.75 MB** | **✅ Soft pass** |
| 50 | 329,161 | 1.49 MB | ✅ Soft pass |

**mc=10 is the minimum viable threshold.** mc=25 is recommended if scoring quality (evaluated separately via the ranking benchmark) is acceptable — it provides considerable headroom within the soft target.

## Reproducibility

To rerun these experiments:

```bash
cd experiments/008-ngram-delivery
pip install brotli
python run_experiment.py 2>&1 | tee ../../experiments.log
```

Input data must be pre-generated:
```bash
python -m pipelines ngram run
```

## Raw Data

- JSON results: `experiments/008-ngram-delivery/data/benchmark_results.json`
- Console log: `experiments/008-ngram-delivery/experiments.log`
