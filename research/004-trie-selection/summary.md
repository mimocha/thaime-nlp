# Trie Data Structure Selection for THAIME

**Date:** 2026-03-08
**Author:** Claude (agent) + Chawit Leosrisook (maintainer)
**Branch:** `research/trie-selection`
**Status:** Complete

## Research Question

Which trie data structure should THAIME use for its production dictionary, given that the critical operation is common prefix search from every character position in the Latin input on every keystroke?

## Approach

We evaluated four trie families through three complementary methods:

1. **Literature survey** — Documented how production IME systems (Google Mozc, librime/RIME, MeCab, kime) use trie data structures for dictionary lookup.
2. **Python benchmarks** — Measured build time, serialized size, memory footprint, and common prefix search latency for four trie implementations at three scale points (10K, 50K, 100K keys) using synthetic data that matches THAIME's expected dictionary shape.
3. **Rust ecosystem evaluation** — Assessed six Rust crate options against THAIME's requirements (common prefix search API, value storage, serialization, maturity, build complexity, license compatibility).

### Synthetic Dataset

Since the real romanization dataset is not yet available, we generated synthetic data matching the expected shape: 3–5 romanization variants per Thai word, ASCII keys of length 3–17 characters, with vowel/consonant substitution variants simulating informal romanization patterns. Three scale points were tested:

| Scale | Words | Total Keys | Unique Keys |
|-------|-------|------------|-------------|
| 10K   | 2,500 | 9,896      | 9,859       |
| 50K   | 12,500| 49,360     | 48,508      |
| 100K  | 25,000| 98,556     | 95,430      |

## Key Findings

### 1. Double-array trie (DARTS) is the best all-around choice for THAIME

The double-array trie provides the optimal balance of search speed, memory efficiency, and ecosystem maturity. It is the same structure used by Google Mozc (Japanese IME) and MeCab (Japanese morphological analyzer) — systems with nearly identical operational requirements to THAIME (common prefix search on Latin-keyed dictionaries at interactive speeds).

### 2. MARISA-trie wins on space but loses on speed

MARISA-trie is ~5× smaller on disk and ~15× smaller in memory than the double-array trie, but ~2–3× slower for common prefix search. For THAIME, where the trie is searched from every character position on every keystroke, search latency matters more than memory. However, if memory becomes a constraint (e.g., on embedded/mobile), MARISA-trie is a viable alternative.

### 3. Standard (pointer-based) trie is fastest in Python but unusable in production

The standard trie has the lowest latency in pure Python benchmarks because Python dict lookup is heavily optimized in CPython. However, its 87 MB memory footprint at 100K keys (vs. 6 MB for double-array, 0.1 MB for MARISA) makes it impractical for production. This result would not transfer to a Rust implementation, where double-array's flat memory layout provides superior cache locality.

### 4. Radix trie offers no advantage for THAIME's key distribution

The pygtrie radix trie was slower than both standard and double-array tries for common prefix search, while offering only modest compression. With ASCII romanization keys of 3–17 characters and high branching factor, path compression provides little benefit. Radix tries excel with long shared prefixes (e.g., URLs, file paths), not short diverse keys.

### 5. The Rust `yada` crate is the top candidate for production

Among Rust crate options, `yada` (static double-array trie, DARTS-clone style) is the most mature and suitable:
- Native `common_prefix_search` API
- Pure Rust (no FFI/C++ dependency)
- 31-bit value storage (sufficient for word IDs)
- MIT/Apache-2.0 license (compatible with THAIME's MPL-2.0)
- Stable API (v0.5.1), ~50K downloads/month

BurntSushi's `fst` crate is a strong alternative if value storage flexibility or automata-based querying is needed.

## Python Benchmark Results

All benchmarks run on the devcontainer environment (Python 3.12), median of 3 runs, 1000 search queries per measurement.

### Common Prefix Search Latency (the critical metric)

| Variant | 10K avg | 10K p99 | 50K avg | 50K p99 | 100K avg | 100K p99 |
|---------|---------|---------|---------|---------|----------|----------|
| Standard Trie | 1.3 µs | 3.5 µs | 2.2 µs | 5.0 µs | 2.5 µs | 5.8 µs |
| Radix Trie (pygtrie) | 7.0 µs | 12.1 µs | 8.9 µs | 17.5 µs | 9.6 µs | 20.6 µs |
| Double-Array (datrie) | 2.5 µs | 4.5 µs | 3.6 µs | 8.3 µs | 4.6 µs | 9.8 µs |
| MARISA-Trie | 8.1 µs | 16.9 µs | 9.7 µs | 20.0 µs | 10.9 µs | 22.2 µs |

**Observation:** All variants are well under the 1 ms target even at 100K keys in Python. In Rust with cache-friendly flat arrays, double-array search will be significantly faster (sub-microsecond expected).

### Serialized Size (on-disk)

| Variant | 10K | 50K | 100K |
|---------|-----|-----|------|
| Standard Trie (pickle) | 441 KB | 2.1 MB | 4.1 MB |
| Radix Trie (pickle) | 326 KB | 1.5 MB | 3.0 MB |
| Double-Array (datrie) | 462 KB | 2.2 MB | 4.3 MB |
| MARISA-Trie | 92 KB | 427 KB | 878 KB |

**Observation:** MARISA-trie is 4.7–5× smaller than double-array on disk. For a 100K-key dictionary, MARISA uses 878 KB vs. 4.3 MB for double-array. Both are acceptable for desktop deployment; MARISA's compactness would matter more for mobile/embedded.

### Memory Footprint

| Variant | 10K | 50K | 100K |
|---------|-----|-----|------|
| Standard Trie | 9.8 MB | 45.7 MB | 87.5 MB |
| Radix Trie (pygtrie) | 5.6 MB | 26.1 MB | 49.8 MB |
| Double-Array (datrie) | 613 KB | 2.9 MB | 5.8 MB |
| MARISA-Trie | 115 KB | 115 KB | 115 KB |

**Observation:** MARISA-trie's memory footprint is essentially constant (~115 KB) because the Python wrapper memory-maps the underlying C++ structure. Double-array is ~50× smaller than standard trie. In Rust, double-array memory footprint would be comparable to serialized size (two flat `u32` arrays).

### Build Time

| Variant | 10K | 50K | 100K |
|---------|-----|-----|------|
| Standard Trie | 0.013 s | 0.119 s | 0.288 s |
| Radix Trie (pygtrie) | 0.066 s | 0.564 s | 1.153 s |
| Double-Array (datrie) | 0.065 s | 0.342 s | 0.780 s |
| MARISA-Trie | 0.030 s | 0.162 s | 0.322 s |

**Observation:** Build time is irrelevant for production (offline construction), but all variants build in under 2 seconds at 100K keys — acceptable for the NLP pipeline.

## Literature Survey: IME Systems and Their Trie Usage

| System | Language | Trie Variant | Purpose | Notes |
|--------|----------|-------------|---------|-------|
| **Google Mozc** | Japanese | DARTS (double-array) | Main conversion dictionary | Static, built offline. Uses `commonPrefixSearch` for lattice construction — same operation THAIME needs. BSD-3-Clause. |
| **MeCab** | Japanese | DARTS (double-array) | Morphological analysis dictionary | Common prefix search for tokenization. Same author as original DARTS. |
| **librime (RIME)** | Chinese | MARISA-trie | Static lexicon index | MARISA for the main read-only dictionary; LevelDB for dynamic user data. Supports prefix search and predictive search. BSD-3-Clause. |
| **kime** | Korean | Rust `HashMap` | Hanja/word dictionary | Simpler dictionary requirements (Hangul→Hanja). No prefix search needed for Korean IME's primary input mode. GPLv3. |

**Key insight:** The two most relevant IME systems to THAIME's architecture (Mozc and MeCab) both use DARTS double-array tries. librime's use of MARISA-trie is motivated by Chinese dictionaries' larger size (millions of entries) where space savings outweigh the speed difference. THAIME's dictionary (30K–150K keys) is closer to Mozc/MeCab's scale.

## Rust Ecosystem Assessment

| Crate | Type | CPS API | Value Storage | Serialization | Maturity | Build | License | Recommendation |
|-------|------|---------|---------------|---------------|----------|-------|---------|----------------|
| **`yada`** | Static double-array (DARTS-clone) | ✅ Native | 31-bit `u32` | Binary blob (can build offline) | Stable (v0.5.1), ~50K dl/mo | Pure Rust | MIT/Apache-2.0 | **⭐ Top pick** |
| **`fst`** | Finite state transducer | ✅ Via Stream range query | `u64` values | Memory-mappable | Very mature, BurntSushi | Pure Rust | MIT/Unlicense | **Strong alternative** |
| **`cedarwood`** | Dynamic double-array (cedar port) | ✅ Native | `i32` values | Custom | Beta (v0.4), ~59K dl/mo | Pure Rust | BSD-2-Clause | Good for user dict |
| **`darts-clone-rs`** | DARTS-clone FFI | ✅ Native | Inherited from C++ | Binary compatible | Stable (C++ core) | C++ FFI | MPL-2.0 | Avoid (FFI complexity) |
| **`darts`** (rust-darts) | Native double-array | ✅ Native | Custom | Custom | Alpha (v0.1) | Pure Rust | MIT | Not production-ready |
| MARISA-trie FFI | MARISA-trie via C | Would need wrapping | Via C API | Memory-mappable | No Rust crate exists | C FFI | LGPL-2.1/BSD | High effort, avoid |

### Detailed Crate Notes

**`yada` (recommended):**
- DARTS-clone style: uses 32-bit elements, DAWG-based construction for suffix merging.
- `common_prefix_search()` returns an allocation-free iterator — ideal for hot-path usage.
- Values are 31-bit unsigned integers. For THAIME, this means storing a word ID (up to ~2 billion) and looking up metadata (confidence, Thai text) in a separate table. This is the standard pattern used by Mozc.
- Can be built from sorted `(key, value)` pairs. The Python pipeline would sort and export; the Rust engine would construct the `DoubleArray` and serialize it as a binary blob for runtime loading.

**`fst` (alternative):**
- Different data structure (finite state transducer, related to DAWG) but solves the same problem.
- Slightly more flexible: `u64` values, supports regex/fuzzy search via automata composition.
- Common prefix search is done via `Stream` range queries — slightly more verbose API but equally efficient.
- Extremely well-maintained by Andrew Gallant (BurntSushi), used in ripgrep and tantivy.
- May be overkill for THAIME's needs, but provides future extensibility (e.g., fuzzy matching for typo tolerance).

**`cedarwood` (niche use):**
- Key differentiator: supports dynamic insertion/deletion, unlike yada/fst.
- Could be useful for THAIME's user dictionary (where users add custom words at runtime).
- Beta quality — not recommended for the main dictionary.

## Recommendation

### Primary: Use `yada` (static double-array trie) for the production Rust engine

1. **Build the dictionary in Python** using the NLP pipeline. Export sorted `(romanization_key, word_id)` pairs as a simple binary format (e.g., sorted TSV or msgpack).
2. **Construct the `yada::DoubleArray`** in a Rust build step from the exported data. Serialize to a binary blob.
3. **Load the binary blob at runtime** in the Rust engine. Use `common_prefix_search()` for Stage 1 lattice construction.
4. **Store metadata separately** — Thai text, confidence weights, n-gram data in a parallel array indexed by `word_id`. The trie maps `romanization_key → word_id`; the metadata table maps `word_id → {thai_text, confidence, ...}`.

### Alternative: Consider `fst` if requirements expand

If THAIME later needs fuzzy matching, regex-based search, or `u64`-range value storage, `fst` provides these capabilities with comparable performance and superior maturity. The transition from `yada` to `fst` would require changing the build step but not the runtime architecture.

### For user dictionaries: Consider `cedarwood`

If THAIME needs a runtime-modifiable dictionary for user-added words, `cedarwood` supports dynamic insertion with `common_prefix_search`. However, a simpler approach (small `HashMap` overlaid on the main trie) may suffice.

### Pipeline format recommendation

The Python NLP pipeline should export:
- **Dictionary data:** Sorted list of `(romanization_key, word_id)` pairs as a flat binary file (e.g., length-prefixed strings + u32 IDs).
- **Metadata table:** `word_id → {thai_text, confidence, romanization_source}` as a separate file (JSON, msgpack, or custom binary).

This clean separation allows the trie format to change (yada → fst → custom) without affecting the pipeline.

## Limitations

1. **Python benchmarks are not directly predictive of Rust performance.** Python's dict-of-dicts trie appears fastest due to CPython's hash table optimization, but this advantage disappears in Rust where flat arrays have superior cache locality. The relative ordering of double-array vs. MARISA should transfer, but absolute numbers will not.

2. **Synthetic data may not match real key distribution.** The synthetic dataset uses algorithmically generated ASCII keys. Real Thai romanization keys may have different character frequency distributions, different amounts of shared prefixes/suffixes, and different variant patterns. Re-benchmarking with real data is recommended once the romanization pipeline is complete.

3. **Value encoding overhead not measured.** Our Python benchmarks encode values as JSON strings inside the trie. In production Rust code, values would be bare `u32` word IDs with zero encoding overhead, making double-array and MARISA faster than measured here.

4. **No Rust benchmarks.** This research explicitly excludes writing Rust code. Actual `yada` vs. `fst` performance comparison should be done in the engine repo when implementation begins.

## Open Questions

1. **Does `yada`'s 31-bit value limit cause problems?** THAIME's dictionary is expected to have 30K–150K keys, well within the 2^31 limit. But if word IDs need to encode additional information (e.g., romanization source ID, confidence tier), 31 bits may be tight. `fst` offers 64-bit values as an alternative.

2. **Can the trie binary be cross-built?** Ideally, the Python pipeline would produce a binary blob that the Rust engine loads directly. `yada` supports building from sorted key-value pairs, but the binary format may need to be generated by Rust code (not Python). A small Rust CLI tool for trie construction may be needed.

3. **How does performance change with real romanization data?** Thai romanization keys may have more shared prefixes (e.g., many words starting with "kh", "th", "ph") than our synthetic data. This could affect both compression ratios and search performance. Re-benchmark when real data is available.

## References

### Trie Data Structures
- Aoe, J. (1989). "An Efficient Digital Search Algorithm by Using a Double-Array Structure." IEEE Transactions on Software Engineering.
- Yata, S. [darts-clone](https://github.com/s-yata/darts-clone) — Static double-array trie (C++).
- Yata, S. [marisa-trie](https://github.com/s-yata/marisa-trie) — MARISA trie (C++).
- Naga, Y. [cedar](http://www.tkl.iis.u-tokyo.ac.jp/~ynaga/cedar/) — Efficiently-updatable double-array trie (C++).

### IME Systems
- [Google Mozc](https://github.com/google/mozc) — Japanese IME, uses DARTS for dictionary (BSD-3-Clause).
- [librime](https://github.com/rime/librime) — Chinese IME engine, uses MARISA-trie for static dictionary, LevelDB for user data (BSD-3-Clause).
- [MeCab](https://taku910.github.io/mecab/) — Japanese morphological analyzer, uses DARTS.
- [kime](https://github.com/Riey/kime) — Korean IME in Rust, uses HashMap for dictionary (GPLv3).

### Rust Crates
- [`yada`](https://crates.io/crates/yada) v0.5.1 — Static double-array trie (MIT/Apache-2.0).
- [`fst`](https://crates.io/crates/fst) — Finite state transducer (MIT/Unlicense).
- [`cedarwood`](https://crates.io/crates/cedarwood) v0.4 — Dynamic double-array trie (BSD-2-Clause).
- [`darts-clone-rs`](https://crates.io/crates/darts-clone-rs) v0.2 — DARTS-clone FFI binding (MPL-2.0).

### Python Libraries Used
- [`marisa-trie`](https://pypi.org/project/marisa-trie/) v1.3.1 — Python bindings for MARISA-trie.
- [`datrie`](https://pypi.org/project/datrie/) v0.8.3 — Python wrapper for libdatrie (double-array).
- [`pygtrie`](https://pypi.org/project/pygtrie/) v2.5.0 — Pure Python trie (Google).
