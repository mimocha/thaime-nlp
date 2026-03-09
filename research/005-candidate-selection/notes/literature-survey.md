# Literature Survey Notes — Candidate Selection in IMEs

## Google Mozc (Japanese IME)

**Source:** https://github.com/google/mozc, https://deepwiki.com/fcitx/mozc

### Architecture
- Strict separation: platform UI ↔ core conversion engine (Protocol Buffers API)
- Core pipeline: Session → Composition → Conversion → Prediction → Rewriter → Output

### Lattice / Scoring
- Constructs directed graph (lattice) from phonetic input
- Nodes = candidate words/phrases; Edges = transitions with costs
- Costs from: unigram/bigram dictionary probabilities, user history, linguistic features
- Viterbi DP finds lowest-cost (highest probability) path
- Post-processing by Rewriter modules for final ranking

### Key Modules
- `converter.cc` / `converter.h` — orchestrates lattice generation, cost assignment, Viterbi
- `DictionaryPredictor` — dictionary-based candidates
- `UserHistoryPredictor` — personalized candidates
- Rewriters — context-dependent transformations

### Relevance to THAIME
- Closest architectural match (DARTS trie + Viterbi)
- Supports unigram-only fallback when bigram unavailable
- Rewriter concept useful for post-MVP feature (re-ranking, normalization)

---

## librime / RIME (Chinese IME Engine)

**Source:** https://github.com/rime/librime, https://deepwiki.com/rime/librime

### Architecture
- Modular, schema-based configuration
- Pipeline: Segmentor → Lattice Builder → Decoder → Ranker → Output

### Lattice / Scoring
- Input segmented into all valid pinyin syllable sequences (lattice/segment graph)
- Greedy longest match + backtracking for segmentation ambiguity
- N-gram LM scoring (configurable)
- Fuzzy/correction rules for typo tolerance
- User learning: frequently used candidates boosted

### Key Classes
- `Lattice` — data structure for decoding paths
- `SegmentGraph` — pinyin segmentation representation
- `PinyinDecoder` — traversal + scoring + pruning

### Relevance to THAIME
- Pinyin segmentation ambiguity directly analogous to THAIME's romanization ambiguity
- Schema-based configurability is a good design pattern for future
- N-gram + user learning = THAIME's upgrade path

---

## libkkc (Japanese Kana-Kanji Converter)

**Source:** https://github.com/ueno/libkkc

### Architecture
- Simpler than Mozc, focused on kana-to-kanji conversion
- Inspired by GNU Emacs kkc.el but with statistical models

### Lattice / Scoring
- Lattice from dictionary segmentation of kana input
- N-gram language model (bigram/trigram from training data) scores edges
- Viterbi finds most probable path
- N-best results for disambiguation

### Relevance to THAIME
- Simpler reference point than Mozc
- Demonstrates that N-gram Viterbi is sufficient for high-quality conversion
- Integration with IBus/Fcitx proves the architecture works with standard IME frameworks

---

## Anthy (Japanese IME)

**Source:** https://github.com/fujiwarat/anthy-unicode, https://deepwiki.com/fujiwarat/anthy-unicode

### Architecture
- Oldest system surveyed (pre-2005 statistical model)
- Lattice from dictionary segmentation with feature-based scoring

### Lattice / Scoring
- Lattice from cannadic dictionary lookup
- Statistical LM introduced 2005 (bigram/trigram)
- Discriminative max-entropy model added 2006
- Feature engineering: POS, length, script type, word probability
- Viterbi path search for best segmentation

### Key Directories
- `src-main` — core conversion
- `src-ordering` — candidate ordering/ranking
- `src-splitter` — input segmentation

### Relevance to THAIME
- Shows minimum viable approach: dictionary + statistical LM + Viterbi
- Feature engineering (POS, length) is a post-MVP enhancement
- Discriminative model is advanced but shows upgrade trajectory

---

## Cross-System Summary

| Aspect | Mozc | librime | libkkc | Anthy |
|--------|------|---------|--------|-------|
| Core algorithm | Viterbi | Viterbi | Viterbi | Viterbi |
| LM type | Unigram+bigram | N-gram (config) | N-gram | Bigram+features |
| Lattice type | DAG (nodes+edges) | Segment graph | Dictionary lattice | Dictionary lattice |
| Top-k support | Yes (rewriter) | Yes (ranked list) | Yes (N-best) | Yes (alternatives) |
| User learning | Yes (predictor) | Yes (user dict) | Limited | Limited |
| Fuzzy matching | Limited | Yes (correction rules) | No | No |

**Universal pattern:** Lattice + Viterbi + statistical LM is the industry standard for IME conversion. All four systems use this approach with varying sophistication levels.
