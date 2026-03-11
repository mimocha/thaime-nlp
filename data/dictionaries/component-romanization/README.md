# Component Romanization Dictionary

**File:** `component-romanization.yaml`

Maps Thai phonological components (onsets, vowels, codas) to their valid informal Latin romanization variants. Used by `src/variant_generator.py` to generate whole-word romanizations via Cartesian product of component variants.

Produced by Research 003 (component-romanization). Validated against 10K words from combined corpora (Change Plan 04, commit 5).

## How It Works

1. TLTK g2p decomposes a Thai word into phonological syllables
2. Each syllable is parsed into onset/vowel/coda components
3. Each component is looked up in this dictionary for variant spellings
4. Whole-word variants are the Cartesian product across all components

Example: กิน → g2p `kin0` → onset `k` + vowel `i` + coda `n` → `{k,g}` × `{i}` × `{n}` → `[gin, kin]`

## Known Limitations

### 1. TLTK ทร → /s/ Misclassification

**Impact:** Loanwords with ทร onset get wrong romanization variants.

TLTK's g2p maps the ทร cluster to /s/ unconditionally. This is correct for native Thai words (ทราย→/saai/, ทราบ→/saap/) where ทร historically merged to /s/, but incorrect for loanwords where ทร is pronounced /tr/:

| Word | Correct | TLTK g2p | Result |
|------|---------|----------|--------|
| ทราย (sand) | /saai/ | `saaj0` | Correct |
| ทราบ (know) | /saap/ | `saap2` | Correct |
| ทรู (True) | /thruu/ | `suu0` | Wrong — gets "s" variants, misses "tr"/"thr" |
| ทริม (trim) | /trim/ | `sim0` | Wrong — gets "s" variants, misses "tr" |
| ทรัมป์ (Trump) | /thramp/ | `sam3` | Wrong — gets "s" variants, misses "tr" |

The dictionary's `thr` onset entry covers **ธร clusters only** (ธ=th + ร=r, e.g., ธรรม), not ทร. This is not fixable at the dictionary level — it requires either TLTK-level fixes or a post-hoc override table mapping known ทร loanwords to their correct pronunciations.

**Scope:** Low. Affects ~10-20 words in the 10K vocabulary (mostly English brand names and loanwords). Users searching for these words would likely type the English spelling directly (e.g., "true", "trim"), which would be handled by a separate loanword lookup table (future work).

### 2. ต Onset Variant Pruning

**History:** The ต onset originally had variants `["t", "d", "dt"]`. At 10K-word scale, the `d` variant produced widespread noise — every ต-initial word generated implausible `d-` romanizations (e.g., ตก→dog, ตอบ→dob, ต้องการ→dongkan). Removed in v0.3.0.

The `dt` variant is kept because:
- It has a systematic origin (Paiboon romanization system)
- It provides disambiguation value between ต (/t/) and ท (/th/)
- It doesn't clash with other onsets the way `d` clashes with ด

### 3. Corpus Noise in 10K Word List

The top-10K frequency list includes non-Thai tokens that produce g2p parsing failures: `ๆ` (mai yamok as standalone token), `xxl`, `ees`, `reek`, etc. These are filtered as TLTK failures (90 out of 10,000) and don't affect dictionary coverage. The dictionary itself does not need entries for these.

### 4. Variant Combinatorial Explosion

Long compound words (4+ syllables) can produce hundreds or thousands of Cartesian product variants. The generator caps output at `max_variants` (default 100 for benchmark generation, 20 for production use). This means some valid variants may be truncated for very long words. The cap is applied after sorting, so alphabetically-first variants are favored.

Future work: statistical co-occurrence pruning could replace the hard cap with probability-weighted selection. See `docs/.plans/change-plan-07-variant-pruning.md`.
