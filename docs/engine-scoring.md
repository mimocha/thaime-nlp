# THAIME Engine: Candidate Selection Scoring

Specification for how the thaime engine (Rust) scores and ranks Thai candidates given a Latin input string. The Python smoke test in `src/utils/smoke_test/` is a reference implementation of this spec.

## Pipeline Overview

Given a Latin input string (e.g., `"malongchaithaime"`), candidate selection has three stages:

1. **Prefix search** — find all dictionary words whose romanization matches a prefix at every position in the input
2. **Viterbi k-best** — build a word lattice (DAG) and find the lowest-cost complete tilings
3. **Deduplication + truncation** — remove duplicate Thai outputs, keep top-K

## Stage 1: Dictionary Prefix Search

The dictionary maps **romanization keys** (Latin strings) to **Thai word entries** (Thai text, frequency, word ID).

- Multiple romanization keys can map to the same Thai word (e.g., `"ma"` and `"maa"` both map to `"มา"`)
- Multiple Thai words can share a romanization key (e.g., `"mai"` maps to `"ไม่"`, `"ไหม"`, `"ใหม่"`)
- Input is **lowercased** before matching

For each character position `start` in the input (0 to len-1), find all romanization keys that are prefixes of `input[start:]`. Each match produces a **lattice edge**:

| Field | Type | Description |
|-------|------|-------------|
| `start` | int | Start position (byte offset) in input |
| `end` | int | End position (`start + len(romanization)`) |
| `thai` | str | Thai word text |
| `frequency` | float | Word frequency from corpus |
| `word_id` | int | Integer ID for n-gram lookup |

When the same word has multiple romanizations of different lengths, each produces a **separate** lattice edge. For example, if `"มา"` has romanizations `["ma", "maa"]` and the input starts with `"maa..."`, both `"ma"` (span 2) and `"maa"` (span 3) create distinct edges.

**Reference implementation:** `TrieData.prefix_match()` in `src/utils/smoke_test/trie_lookup.py`

## Stage 2: Viterbi K-Best

### Scoring Formula

**Edge cost** (cost of adding one word to a path):

```
unigram_cost = -ln(max(frequency, MIN_FREQ)) + LAMBDA
ngram_bonus  = NGRAM_WEIGHT * -ln(max(stupid_backoff_score, 1e-20))
edge_cost    = unigram_cost + ngram_bonus
```

**Path cost** (total cost of a complete tiling):

```
path_cost = sum of edge_costs for all words in the path
```

**Lower cost = better candidate.**

The `frequency` in `unigram_cost` is the **trie entry frequency** (word frequency from corpus). The `stupid_backoff_score` is a **linear probability** returned by the n-gram model (see Stage 3). When n-gram data is unavailable, `ngram_bonus = 0`.

Note: costs use **natural log (ln)**, not log10. The n-gram binary stores log10 probabilities, but the conversion to linear probability happens inside the Stupid Backoff scorer before the cost transformation.

### Parameters

Source: `config.rs` in the thaime engine.

| Parameter | Default | Description |
|-----------|---------|-------------|
| LAMBDA | 1.0 | Segmentation penalty per word |
| MIN_FREQ | 5e-6 | Floor for word frequency (avoids -ln(0)) |
| K | 10 | Candidates to track per state / final output count |
| NGRAM_WEIGHT | 2.0 | Multiplier for n-gram cost component |
| ALPHA | 0.4 | Stupid Backoff penalty factor |
| BEAM_MULTIPLIER | 4 | Global beam width = K * BEAM_MULTIPLIER |
| FLOOR_PROB | 6e-6 | Floor probability for unseen n-gram words |

### Forward Pass

The Viterbi state at each lattice position is keyed by `(prev_word_2, prev_word_1)` — the Thai text of the two most recent words. This provides trigram context for n-gram scoring.

**Initialization** (position 0): one empty path with cost 0 and state `(None, None)`.

**For each position `end` from 1 to input_length:**

1. For each lattice edge ending at `end` (spanning `[start, end)`):
2. For each existing partial path at position `start`:
3. Compute `edge_cost` using the formula above
4. Create a new partial path at position `end` with:
   - `cost = old_path.cost + edge_cost`
   - `state = (old_path.prev_word_1, current_edge.thai)`

**Pruning** (applied at each position after extending paths):

1. **Per-state:** For each `(prev_word_2, prev_word_1)` state, sort by cost ascending and keep top K
2. **Global beam:** If total paths across all states exceeds K * BEAM_MULTIPLIER, flatten, sort by cost, keep top K * BEAM_MULTIPLIER, redistribute into state buckets

### Result Collection

After the forward pass:

1. Collect all complete paths at final position
2. Sort by cost ascending (lower = better)
3. Deduplicate by Thai output string, keeping the lowest-cost instance
4. Truncate to K candidates

**Reference implementation:** `beam_search()` in `src/utils/smoke_test/viterbi.py`

## Stage 3: Stupid Backoff N-gram Scoring

The n-gram model stores pre-computed **log10 conditional probabilities** in a binary file (TNLM v1 format, see `docs/handover-ngram-binary-v1.md`):

- Unigrams: `log10(P(w))`
- Bigrams: `log10(P(w2|w1))`
- Trigrams: `log10(P(w3|w1,w2))`

The scoring interface returns a **linear probability** (not log), which the Viterbi pass converts to cost via `-ln(score)`.

### Backoff Chain

```
trigram_score(prev2, prev1, w):
    if prev2 and prev1 both available:
        if trigram(prev2, prev1, w) exists:  return 10^trigram
        else:  return ALPHA * bigram_score(prev1, w)      # had context, penalize
    else:
        return bigram_score(prev1, w)                      # BOS, no penalty

bigram_score(prev, w):
    if prev available:
        if bigram(prev, w) exists:  return 10^bigram
        else:  return ALPHA * unigram_prob(w)              # had context, penalize
    else:
        return unigram_prob(w)                             # BOS, no penalty

unigram_prob(w):
    if unigram(w) exists:  return 10^unigram
    else:  return FLOOR_PROB
```

**Key rule:** The alpha penalty is only applied when backing off from a level where context **was available** but no n-gram entry was found. At BOS (beginning of sentence, when context is `None`), there is **no alpha penalty**.

**Reference implementation:** `NgramModel.trigram_score()`, `NgramModel.bigram_score()`, `NgramModel.unigram_prob()` in `src/utils/smoke_test/ngram_score.py`

## Notes

- **Byte vs character positions:** The Rust engine uses byte offsets for lattice positions. Romanization keys are ASCII-only, so Python `len(key)` equals byte length. This only matters if non-ASCII romanizations are ever added.
- **Precision:** The Rust engine stores log10 probabilities as f32. The Python smoke test reads these same f32 values, so there is minor f64-to-f32-to-f64 round-trip precision loss. This is acceptable for verifying the rank-1 candidate.
- **Context:** The engine supports committed context (previous words from earlier conversions). For standalone smoke testing, context is always empty (`None, None`).
