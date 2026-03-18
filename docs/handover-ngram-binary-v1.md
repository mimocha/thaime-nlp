# THAIME N-gram Binary Format — v1

Specification for the binary language model file produced by the thaime-nlp pipeline and consumed by the thaime engine (native Linux IME and WASM web demo).

## Overview

The binary stores pre-scored log₁₀-probabilities for unigrams, bigrams, and trigrams. The engine performs simple table lookups — no runtime smoothing math is needed. Backoff chains (e.g., Stupid Backoff) are handled by falling back to lower-order lookups when higher-order entries are missing.

**File naming:** `thaime_ngram_v{format_version}_mc{min_count}.bin`

Example: `thaime_ngram_v1_mc20.bin`

## Header (32 bytes, little-endian)

```
Offset  Size  Type   Field            Description
------  ----  ----   -----            -----------
0x00    4     [u8;4] magic            "TNLM" (0x544E4C4D)
0x04    2     u16    format_version   Binary layout version (currently 1)
0x06    2     u16    flags            Reserved bitfield (0 for v1)
0x08    2     u16    vocab_size       String table entry count
0x0A    1     u8     smoothing        Enum: 0=StupidBackoff, 1=MKN, 2=Katz
0x0B    1     u8     min_count        N-gram count threshold used
0x0C    4     u32    n_unigrams       Number of unigram entries (= vocab_size)
0x10    4     u32    n_bigrams        Number of bigram entries
0x14    4     u32    n_trigrams       Number of trigram entries
0x18    4     f32    alpha            Backoff weight (e.g. 0.4)
0x1C    4     u32    build_info       Upper 16 bits: Unix days since epoch
                                      Lower 16 bits: git hash prefix
```

### Rust header struct

```rust
#[repr(C, packed)]
struct NgramHeader {
    magic: [u8; 4],
    format_version: u16,
    flags: u16,
    vocab_size: u16,
    smoothing: u8,
    min_count: u8,
    n_unigrams: u32,
    n_bigrams: u32,
    n_trigrams: u32,
    alpha: f32,
    build_info: u32,
}
```

### Validation on load

1. Check `magic == b"TNLM"`.
2. Check `format_version == 1` (reject unknown versions).
3. Check `n_unigrams == vocab_size` (invariant for v1).
4. Log header fields for debugging: `vocab_size`, `smoothing`, `min_count`, `alpha`, decoded `build_info`.

### Build info decoding

```rust
let unix_days = (header.build_info >> 16) as u16;
let git_hash  = (header.build_info & 0xFFFF) as u16;
// unix_days * 86400 → approximate build timestamp (UTC)
// git_hash → first 4 hex chars of commit hash
```

## Body Layout

### String Table

Immediately follows the header. Variable-length, read sequentially.

```
For each word (vocab_size entries, ordered by word_id 0..vocab_size-1):
    len:  u8           — byte length of UTF-8 string (max 255)
    data: [u8; len]    — UTF-8 encoded Thai word
```

Thai words are typically 3–12 UTF-8 bytes, so u8 length is sufficient.

### Rust string table reader

```rust
fn read_string_table(reader: &mut impl Read, vocab_size: usize) -> Vec<String> {
    let mut table = Vec::with_capacity(vocab_size);
    for _ in 0..vocab_size {
        let mut len_buf = [0u8; 1];
        reader.read_exact(&mut len_buf).unwrap();
        let len = len_buf[0] as usize;
        let mut buf = vec![0u8; len];
        reader.read_exact(&mut buf).unwrap();
        table.push(String::from_utf8(buf).unwrap());
    }
    table
}
```

### Unigrams

```
f32[vocab_size]    — log₁₀(P(w)) indexed by word_id
```

Every word in the vocabulary has an entry. Words that didn't meet the quality threshold during encoding receive a floor value (approximately `log₁₀(1/total_tokens)`).

### Bigrams

```
(u16 w1, u16 w2, f32 score)[n_bigrams]    — 8 bytes per entry
```

Sorted by `(w1, w2)` ascending for binary search. Score is `log₁₀(P(w2|w1))`.

### Trigrams

```
(u16 w1, u16 w2, u16 w3, u16 _pad, f32 score)[n_trigrams]    — 12 bytes per entry
```

Sorted by `(w1, w2, w3)` ascending for binary search. `_pad` is always 0 and exists to ensure `f32` alignment. Score is `log₁₀(P(w3|w1,w2))`.

## Lookup and Backoff

The engine implements backoff in the scorer, not in the binary. For Stupid Backoff with α=0.4:

```rust
fn score_bigram(&self, w1: u16, w2: u16) -> f32 {
    match self.lookup_bigram(w1, w2) {
        Some(score) => score,
        None => LOG10_ALPHA + self.unigrams[w2 as usize],
    }
}

fn score_trigram(&self, w1: u16, w2: u16, w3: u16) -> f32 {
    match self.lookup_trigram(w1, w2, w3) {
        Some(score) => score,
        None => LOG10_ALPHA + self.score_bigram(w2, w3),
    }
}

// LOG10_ALPHA = log10(0.4) ≈ -0.39794
```

### Binary search for bigrams

```rust
fn lookup_bigram(&self, w1: u16, w2: u16) -> Option<f32> {
    self.bigrams
        .binary_search_by_key(&(w1, w2), |entry| (entry.w1, entry.w2))
        .ok()
        .map(|idx| self.bigrams[idx].score)
}
```

### Binary search for trigrams

Same pattern with `(w1, w2, w3)` as the key.

## Delivery

- **WASM (web demo):** Serve the `.bin` file compressed with brotli. Modern browsers decompress automatically via `Content-Encoding: br`.
- **Native (Linux IME):** Load the raw `.bin` file directly (no decompression needed). Memory-map or read into a Vec.

### Size targets (measured from pipeline output)

| min_count | Raw size | Brotli (q9) |
|-----------|----------|-------------|
| 15        | 9.81 MB  | 5.42 MB     |
| 20        | 7.48 MB  | 4.18 MB     |
| 25        | 6.09 MB  | 3.43 MB     |

Target: brotli < 5 MB. mc=20 is the recommended default.

## Future Compatibility

- `format_version` is bumped when the binary layout changes structurally.
- Smoothing method changes that only affect score values do **not** require a format version bump.
- The `flags` field and header extension are reserved for future smoothing parameters (MKN discount values, etc.).
- The engine should reject `format_version > 1` until it implements the newer parser.
