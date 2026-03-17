# N-gram Data Delivery Format: Background Research & Experimental Plan

**Topic:** research/008-ngram-delivery
**Date:** 2026-03-18
**Author:** THAIME Research (agent + maintainer)
**Status:** DRAFT (Stage 1+2 combined)

---

## Problem Statement

The THAIME engine uses trigram→bigram→unigram Stupid Backoff scoring (Research
007), but n-gram data is currently stored as raw TSV files totaling ~370 MB. This
is acceptable for development but unusable for production deployment:

- **Native (Linux IME):** Data is embedded via `include_bytes!` or loaded from
  disk at startup. 370 MB is far too large for either approach.
- **WASM (web demo):** Data must be fetched over HTTP. Even gzip'd, raw TSV is
  impractical for web delivery.

We need to identify a compact binary format that satisfies both deployment
targets. This research surveys candidate formats, then benchmarks them on the
metrics that matter (size, compressibility, and structural properties) to narrow
the field to 1–2 finalists for production implementation.

### Source data

Produced by the n-gram pipeline (`python -m pipelines ngram run`). All outputs
are in `pipelines/outputs/ngram/`:

| Level   | File                          | Raw entries | After min_count=10 | TSV size |
|---------|-------------------------------|------------|---------------------|----------|
| Unigram | `ngrams_1_merged_raw.tsv`     | 16K        | 16K                 | 366 KB   |
| Bigram  | `ngrams_2_merged_raw.tsv`     | 2.6M       | 736K                | 88 MB    |
| Trigram | `ngrams_3_merged_raw.tsv`     | 6.4M       | 806K                | 284 MB   |

Vocab size is ~16K Thai words (fits in u16). Counts are u32 (max observed count
is well within 2^32).

### Scoring interface requirements

The binary format must support the Stupid Backoff query pattern:

```
score(w3 | w1, w2):
  if count(w1, w2, w3) > 0: return count(w1,w2,w3) / count(w1,w2)
  elif count(w2, w3) > 0:   return alpha * count(w2,w3) / count(w2)
  else:                     return alpha^2 * P_unigram(w3)
```

This means the format must support:
1. **Point lookup:** Given an n-gram key (1–3 words), return its count or score.
2. **Prefix context lookup:** Given a context (w1, w2), enumerate or look up all
   continuations — or at minimum, look up a specific continuation efficiently.

---

## Background Research

### Established n-gram storage formats

#### ARPA format

The standard text-based format for n-gram language models, used by SRILM and
most LM toolkits. Stores `log-prob \t ngram \t backoff-weight` per line,
organized by n-gram order. Human-readable but large (comparable to raw TSV).
Not a binary format — included as a reference point since many tools can
import/export it.

**Relevance:** Not directly useful for production, but understanding ARPA
clarifies what information a format needs to carry (probabilities vs. raw counts,
backoff weights).

#### KenLM (probing hash + trie)

The most widely-deployed binary n-gram format. KenLM offers two structural
families with six total model types:

- **Probing hash table:** Open-addressing hash map with linear probing and
  64-bit keys (hashed n-gram). O(1) lookup, ~50% space overhead (1.5× load
  factor). Effective cost is ~24 bytes per n-gram entry (16 bytes/entry × 1.5
  multiplier). Fast but not space-optimal. Unigrams are stored in a separate
  direct-access array indexed by vocabulary ID, not in the hash table. Does
  **not** support quantization — always stores full 32-bit floats. Variants:
  PROBING, REST_PROBING.
- **Trie:** N-gram entries stored in sorted arrays, one level per order.
  Bigrams are children of their unigram prefix, trigrams children of their bigram
  prefix. Uses **interpolation search** (not binary search) within each prefix
  group — O(log log N) average case. Key space-saving features: **bit-level
  packing** (word indices use the minimum bits needed for the vocab size) and
  optional **Bhiksha pointer compression** (chopping leading bits from child
  pointers). Supports **quantized probabilities** from 1 to 25 bits (not just
  8/16), independently configurable for probabilities and backoff weights.
  Variants: TRIE, QUANT_TRIE, ARRAY_TRIE, QUANT_ARRAY_TRIE.

Both families use vocabulary-mapped integer IDs (similar to our u16 word IDs).
Binary files are loaded via `mmap`, so the OS manages paging and the full model
need not fit in RAM.

**Relevance:** KenLM's trie structure is directly applicable. The quantization
technique (mapping log-probs to discrete buckets) is worth benchmarking. The
probing hash is essentially our E1 candidate below.

Source: Heafield 2011, "KenLM: Faster and Smaller Language Model Queries"

#### Minimal perfect hashing (MPH)

Maps a known key set to [0, N) with no collisions and no wasted slots. Lookup is
O(1) with 2–3 hash evaluations (algorithm-dependent). Space overhead varies by
algorithm: CHD ~2.07 bits/key, PtrHash ~2.4 bits/key, BBHash ~3.7 bits/key at
default gamma (theoretical lower bound: ~1.44 bits/key). The value array is
stored separately, indexed by the hash output.

Rust libraries:
- `ptr_hash` — PtrHash algorithm (SEA 2025). Current state-of-the-art: fastest
  construction and query, ~2.4 bits/key. Best choice for large runtime key sets.
- `ph` — FMPH/FMPHGO algorithms (ALENEX 2026). Another strong modern option.
- `boomphf` — BBHash algorithm. Maintained by 10x Genomics. Uses ~3.7 bits/key;
  no longer state-of-the-art but well-tested.
- `phf` — CHD algorithm, compile-time only. Designed for small-to-moderate
  static maps embedded via proc macros. **Not practical for 800K+ keys** (would
  embed the entire hash structure at compile time).
- `cmph` (C library) — canonical C MPHF library, supports CHD/BDZ/BMZ. LGPL-2.

Build time at 800K keys is a **non-issue** with modern libraries: PtrHash takes
~16–40 ms, BBHash <100 ms. The concern only applies at tens-of-millions scale.

**Relevance:** Attractive for our use case since the key set is static and known
at build time. The main concern is whether the hash function description itself
compresses well (random-looking bits don't compress). Prior art: Talbot & Brants
2008 demonstrated MPH-based n-gram LMs; Guthrie et al. 2010 achieved ~2.5
bytes per n-gram using multi-level MPH with frequency counts.

#### Double-array trie (DARTS)

Research 004 evaluated DARTS for the word trie and recommended `yada` for
production. A DARTS structure could also be used for n-gram lookup if n-gram keys
are encoded as concatenated word IDs.

**Relevance:** Possible but awkward — DARTS is optimized for prefix search over
byte sequences, not tuple lookup. Would require encoding (u16, u16, u16) keys as
byte strings. Likely not the best fit for pure point-lookup workloads.

#### Flat sorted arrays + binary search

The simplest binary approach: sort n-gram entries by key, store as a flat array
of fixed-size records, and use binary search for lookup. O(log N) per query.
Can be memory-mapped on native platforms (zero deserialization cost).

**Relevance:** Simple to implement, very compact on disk, compresses well
(sorted data has low entropy deltas). The key question is whether O(log N) is
fast enough — for 800K trigrams, that's ~20 comparisons per lookup.

#### Variable-length encoding / delta compression

Store sorted n-gram IDs as deltas from the previous entry, then apply
variable-length integer encoding (varint, Simple8b, etc.). This exploits the
low-entropy nature of sorted integer sequences to reduce size further.

**Relevance:** A refinement applicable on top of flat sorted arrays. Adds
decoding complexity but can significantly reduce compressed size. Note that
**Elias-Fano encoding** is a strictly superior variant: it achieves near-optimal
compression of sorted integer sequences (~n × (2 + log(U/n)) bits for n
integers from universe [0, U)) while providing O(1) random access via
rank/select — no sequential decoding or block indexing needed. See the
`tongrams-rs` entry below for a purpose-built implementation.

#### FST map (finite state transducer)

A minimal acyclic finite-state transducer that maps byte-string keys to u64
values. Exploits shared prefixes and suffixes in the key set for extreme
compression — often smaller than gzip of the raw data. O(key_length) lookup;
supports prefix iteration via automaton-based search.

For n-gram storage: encode trigram keys as 6-byte strings (3 × u16 big-endian)
and map to u32 counts stored as u64 values. "All trigrams starting with (w1,w2)"
becomes a natural byte-prefix query.

The `fst` crate (BurntSushi) is a battle-tested Rust implementation used in
`tantivy` (Rust search engine). Pure Rust, no unsafe, likely WASM-compatible.
Build time is O(n) for pre-sorted input. The FST is immutable once built (fine
for static data).

**Relevance:** Strong candidate. Compact storage, fast lookup, native prefix
iteration for context queries. The main question is whether the FST's internal
compression interacts well with brotli on top (since the FST is already
compressed, brotli may yield diminishing returns).

#### Elias-Fano trie (tongrams-rs)

A purpose-built n-gram storage structure from Pibiri & Venturini (SIGIR 2017,
ACM TOIS 2019). N-grams are stored in a trie where each level's child pointers
and values are compressed with Elias-Fano encoding. Achieves ~2.6 bytes per
n-gram (across all orders) on standard datasets.

The `tongrams-rs` crate is a Rust port of the C++ `tongrams` library. Pure
Rust. Supports point lookup and prefix enumeration via the trie structure. WASM
compatibility is likely (no system calls or unsafe mmap).

**Relevance:** The most directly relevant existing solution — built specifically
for n-gram LM storage. If it supports our count-lookup query pattern and
compiles to WASM, it could be a near-drop-in solution. At minimum, the
Elias-Fano trie approach deserves benchmarking.

### Summary of landscape

| Approach               | Lookup       | Size efficiency          | Compressibility | Complexity | Prefix query |
|------------------------|--------------|--------------------------|-----------------|------------|--------------|
| Probing hash (KenLM)   | O(1)         | Moderate (50% overhead)  | Poor (random)   | Low        | No           |
| Trie (KenLM)           | O(log log N) | Good (bit-packed)        | Good            | Medium     | Yes (trie)   |
| MPH (`ptr_hash`)        | O(1)         | Very good (~2.4 bits/key)| Poor (hash bits)| Medium     | No           |
| Flat sorted array      | O(log N)     | Very good                | Very good       | Very low   | Via scan     |
| DARTS                  | O(key len)   | Good                     | Moderate        | High       | Yes (trie)   |
| Delta + varint         | O(log N)*    | Excellent                | Excellent       | Medium     | No           |
| FST map (`fst` crate)  | O(key len)   | Excellent                | Moderate†       | Low        | Yes (automaton) |
| Elias-Fano trie (`tongrams-rs`) | O(1)/level | Excellent (~2.6 B/gram) | Moderate† | Medium | Yes (trie) |

*Lookup requires sequential decoding unless combined with block indexing or
Elias-Fano encoding (which provides O(1) random access).

†FST and Elias-Fano are already internally compressed, so external compression
(gzip/brotli) may yield diminishing returns compared to formats that store raw
sorted data.

---

## Candidate Encodings

Based on the background research, these are the formats to benchmark:

### E1: Word-ID flat arrays → HashMap at load time

Assign each word a `u16` ID via a string table. Store n-grams as packed arrays
of fixed-size tuples. At load time, deserialize into a HashMap (same runtime
structure as the current TSV-based approach, but with a compact binary on-disk
representation).

- Unigrams: `[u32_count; N]` indexed directly by word ID
- Bigrams: `[(u16_w1, u16_w2, u32_count); N]`
- Trigrams: `[(u16_w1, u16_w2, u16_w3, u32_count); N]`
- String table: length-prefixed UTF-8, ID = array index

**Tradeoff:** Small on disk, but load time includes HashMap construction.
Memory footprint at runtime equals the HashMap size, not the file size.

### E2: Word-ID flat arrays + binary search (zero-copy)

Same on-disk format as E1, but at runtime the sorted arrays stay in memory
as-is. Lookups use binary search over the packed tuples. On native Linux, this
can be `mmap`'d for zero-copy loading (not applicable in WASM, where the full
buffer must be in memory).

**Tradeoff:** Fastest possible load time (no deserialization). O(log N) lookup
instead of O(1), but N ≤ 806K means ≤ 20 comparisons.

### E3: Quantized log-probabilities

Pre-compute conditional log-probabilities and quantize into discrete buckets.
Store as sorted tuples with the count field replaced by a quantized score.

Two sub-variants to test:
- **E3a (u8, 256 buckets):** Smallest possible value field. Expected precision
  loss ~0.4% (1/256).
- **E3b (u16, 65536 buckets):** Higher precision, negligible quantization error.

Quantization can be uniform or non-uniform (log-spaced or learned from the data
distribution). Both should be compared.

**Tradeoff:** Smaller values (especially u8) at the cost of losing raw counts.
The backoff penalty alpha must be baked in at build time, or stored as a separate
parameter.

### E4: Minimal perfect hash (MPH)

Use a minimal perfect hash function to map n-gram keys to a dense value array.
O(1) lookup with no wasted slots. Separate MPH per n-gram level. In Rust, the
`ptr_hash` crate (~2.4 bits/key, fastest available) is the recommended
implementation.

**Tradeoff:** Best lookup performance and no space wasted on empty hash buckets.
The hash function description uses ~2.4 bits/key (may not compress well since
the bits look random). Build time is negligible at 800K keys (<100 ms). Values
can be raw counts or quantized log-probs. Does not support prefix enumeration
(no way to list all continuations of a context without trying all vocabulary
items).

### E5: Baseline — TSV → HashMap (status quo)

The current approach: load raw TSV at startup, parse strings, build HashMaps.
Included to quantify the improvement of binary formats.

### E6: FST map (BurntSushi `fst` crate)

Encode n-gram keys as fixed-length byte strings (2 bytes per u16 word ID,
big-endian) and build an FST map from key → count. Separate FST per n-gram
level, or a single FST with a level-prefix byte.

- Trigram key: 6 bytes (w1‖w2‖w3), value: u64 (count as u64)
- Bigram key: 4 bytes (w1‖w2), value: u64
- Unigram key: 2 bytes (w1), value: u64

The FST exploits shared prefixes/suffixes across keys for compression. Prefix
iteration supports "all continuations of (w1, w2)" natively.

**Tradeoff:** Excellent compression, fast lookup, native prefix queries. But the
FST is already internally compressed, so brotli on top may not help much. The
Python experiment would use the `fst` PyPI package or a pure-Python FST builder
to measure the on-disk size; actual Rust performance uses the `fst` crate
directly.

### E7: Elias-Fano trie (tongrams-rs approach)

Store n-grams in a trie structure where each level's sorted word-ID sequences
and count values are compressed using Elias-Fano encoding. This is the approach
used by `tongrams-rs` (Pibiri & Venturini, SIGIR 2017).

For the Python experiment, implement a simplified Elias-Fano encoder: store
sorted integer sequences using high-bits/low-bits splitting with a bitvector for
the high bits. Measure the resulting binary size and compressibility.

**Tradeoff:** Near-optimal space (~2.6 bytes/n-gram in published benchmarks).
O(1) random access within each trie level via rank/select. More complex to
implement than flat arrays, but `tongrams-rs` provides a ready-made Rust
implementation for production. Like E6, internal compression may reduce brotli
gains.

---

## Experimental Plan

### Variables

| Variable         | Values                                       | Description |
|------------------|----------------------------------------------|-------------|
| Encoding format  | E1, E2, E3a, E3b, E4, E5 (baseline), E6, E7 | Binary format under test |
| min_count        | 2, 5, 10, 25, 50 (bigrams+trigrams)          | Count threshold for n-gram inclusion |
| Quantization     | uniform, log-spaced (E3 only)                | Bucket spacing strategy |

### Metrics

All metrics below can be measured in Python without Rust tooling:

| Metric                 | Method                                             | Unit    |
|------------------------|----------------------------------------------------|---------|
| **Encode time**        | Wall clock for TSV → binary file                   | seconds |
| **File size (raw)**    | `os.path.getsize()` on the binary output           | bytes   |
| **File size (gzip)**   | `gzip -9` via Python `gzip` module                 | bytes   |
| **File size (brotli)** | `brotli -9` via Python `brotli` module             | bytes   |
| **Decode time**        | Wall clock for binary → queryable Python structure  | seconds |
| **Correctness**        | Score parity vs. E5 baseline on a reference query set | % match |
| **Quantization error** | Mean/max absolute error vs. exact log-prob (E3 only) | float   |

Metrics **not** measured in this research (deferred to engine-side validation):
- Query latency in ns (requires Rust `criterion` benchmarks)
- RSS / heap memory in Rust
- WASM-specific load time

These are deferred because Python timings don't predict Rust performance for
HashMap vs. binary search vs. PHF. However, the **relative size and compression
ratios** measured here will transfer directly — a format that's 3× smaller in
Python will be 3× smaller in Rust.

### Data source

Input TSV files from `pipelines/outputs/ngram/`:
- `ngrams_1_merged_raw.tsv` (unigrams)
- `ngrams_2_merged_raw.tsv` (bigrams)
- `ngrams_3_merged_raw.tsv` (trigrams)

These are regenerated by running `python -m pipelines ngram run` in the
devcontainer. The raw-count merge is used (not the normalized merge), since
Stupid Backoff operates on raw counts.

### Procedure

**Phase 1: Encoding implementation**

1. Load the n-gram TSV files; build the word→ID string table (u16 mapping).
2. Implement a Python encoder for each format (E1–E4, E6–E7) that writes the
   binary representation to a file.
3. Implement a Python decoder for each format that reads the binary file back
   into a queryable structure.
4. Verify round-trip correctness: for each format, decode the binary and confirm
   that all n-gram lookups return the expected count (or acceptably close score
   for quantized formats).

**Phase 2: Size benchmarking**

5. For each encoding × min_count combination, generate the binary file.
6. Measure raw file size, gzip-compressed size, and brotli-compressed size.
7. Record encode time and decode time.
8. Produce a **size matrix** (rows: encoding × min_count, columns: raw / gzip /
   brotli / entry count).

**Phase 3: Quantization analysis (E3 only)**

9. Compute exact log-probabilities from raw counts.
10. Apply uniform and log-spaced quantization at u8 and u16 precision.
11. Measure quantization error distribution (mean, p95, max absolute error).
12. Verify that quantized scores preserve the same ranking order as exact scores
    on a sample of 10K query contexts.

**Phase 4: Synthesis**

13. Identify which formats meet the hard size constraint (brotli ≤ 10 MB).
14. Among those, compare on compressed size, encode/decode time, and
    implementation complexity.
15. Recommend 1–2 finalist formats for Rust implementation.

### Success criteria

**Hard constraints (must pass to be a viable candidate):**
- Brotli-compressed total size (uni+bi+tri) ≤ 10 MB
- Round-trip correctness: 100% exact match for non-quantized formats
- Quantization rank preservation: ≥ 99% of pairwise orderings preserved

**Soft preferences (for choosing among viable candidates):**
- Brotli total size < 5 MB
- Single-file format (or trivially concatenable)
- Preserves raw counts (enables runtime alpha tuning)
- Simple implementation (fewer things to get wrong in Rust)

### Dependencies

Python packages (all available in the devcontainer or via pip):
```
brotli        # Brotli compression measurement
```

All other dependencies (`struct`, `gzip`, `hashlib`, etc.) are in the standard
library. No Rust tooling required for this research.

### Estimated effort

- Phase 1 (encoding implementations): ~1 session
- Phase 2 (size benchmarking): ~1 session (mostly automated once encoders work)
- Phase 3 (quantization analysis): included in Phase 2 session
- Phase 4 (synthesis + write-up): ~0.5 session

---

## Expected Output

A `results.md` with:

1. **Size matrix** — encoding × min_count, showing: entry count, raw size, gzip
   size, brotli size, encode time, decode time.
2. **Compression ratio chart** — visualizing which formats compress best.
3. **Quantization error analysis** — for E3a/E3b, distribution of errors and
   rank-preservation rate.
4. **Recommendation** — 1–2 finalist formats with rationale, ready for Rust
   implementation in the thaime engine repo.

---

## Out of Scope

- **Query latency benchmarking** — Requires Rust/criterion. Deferred to engine
  validation (see Follow-up below).
- **Scoring quality / MRR impact** of different min_count thresholds — Separate
  evaluation concern using the ranking benchmark.
- **N-gram data generation** — Handled by the existing `pipelines/ngram/`
  pipeline.
- **WASM-specific async loading** — UX concern, not a format concern.

### Formats considered but excluded

The following were evaluated during background research and excluded:

- **Bloom filter LMs (RandLM)** — Lossy (false positives); does not support
  prefix enumeration; unnecessary since our data is small enough for lossless
  formats.
- **FlatBuffers / Cap'n Proto / Protocol Buffers** — General-purpose
  serialization frameworks. Alignment padding (FlatBuffers/Cap'n Proto) inflates
  size vs. tightly-packed arrays; Protobuf requires full deserialization. No
  advantage over E1/E2 for this fixed-schema, lookup-heavy workload.
- **OpenFst / rustfst** — Heavyweight general FST framework designed for
  composition/determinization operations, not optimized for simple point lookups.
  The BurntSushi `fst` crate (E6) is a better fit for our read-only map use case.
- **LOUDS trie** — Interesting succinct structure (~2n+1 bits for n nodes), but
  `tongrams-rs` (E7) captures the same trie idea with a more mature, n-gram-
  specific implementation.
- **Wavelet trees** — O(log σ) per operation with σ=16K vocabulary makes each
  query touch 14+ bitvector levels. Slower than binary search at our data size,
  and far more complex to implement.

---

## Follow-up: Engine-side Validation

> This section documents the work that follows this research, to be carried out
> in the main `thaime` engine repository. It is included here so the full
> delivery plan is documented in one place.

Once this research identifies 1–2 finalist formats:

**Stage A: Rust implementation**

Implement the chosen format(s) in the thaime engine as a Rust module. This
includes:
- Binary encoder (build script or standalone CLI that reads TSV → writes binary)
- Binary decoder (loaded at engine startup via `include_bytes!` or file read)
- Integration with the existing `NgramScorer` trait

**Stage B: Performance benchmarking**

Using Rust `criterion` benchmarks in the engine repo, measure:
- Query latency (p50, p99) for hits, partial hits, and full misses
- Load/decode time from bytes → queryable structure
- Steady-state memory (RSS or jemalloc allocated)

If multiple finalist formats are implemented, produce a performance comparison
and select the final winner.

**Stage C: WASM validation**

Build the engine for `wasm32-unknown-unknown` with the chosen format. Measure:
- Compressed transfer size (brotli, as served by CDN)
- Load + decode time in a browser environment
- Query latency under wasm-bindgen

**Stage D: Integration**

Replace the TSV loading path with the binary format. Update the n-gram pipeline
in this repo to include a binary export step (`pipelines/ngram/encode.py` or
similar) so that pipeline runs produce deploy-ready binary artifacts alongside
the TSV files.

---

## Sources

- Heafield 2011, "KenLM: Faster and Smaller Language Model Queries"
- Talbot & Brants 2008, "Randomized Language Models via Perfect Hash Functions"
- Guthrie, Hepple & Liu 2010, "Efficient Minimal Perfect Hash Language Models"
- Pibiri & Venturini 2017, "Efficient Data Structures for Massive N-Gram
  Datasets" (SIGIR 2017, ACM TOIS 2019)
- Research 004: Trie Data Structure Selection (DARTS evaluation)
- Research 007: N-gram Transition Probability (Stupid Backoff recommendation)
- N-gram pipeline: `pipelines/ngram/` (this repo)
- KenLM source: https://github.com/kpu/kenlm
- `ptr_hash` crate — PtrHash MPHF (SEA 2025)
- `fst` crate (BurntSushi) — FST map: https://github.com/BurntSushi/fst
- `tongrams-rs` — Elias-Fano n-gram tries: https://github.com/kampersanda/tongrams-rs
- `boomphf` crate documentation (BBHash minimal perfect hashing)
