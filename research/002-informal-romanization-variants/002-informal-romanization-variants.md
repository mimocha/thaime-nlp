# Research Task 002: Informal Thai Romanization Variant Generation

## Metadata

- **Task ID:** 002
- **Topic:** Rule-based generation of informal romanization variants from formal base romanizations
- **Branch:** `research/002-informal-romanization-variants`
- **Status:** Proposed
- **Dependencies:** Task 001 (Romanization Source Audit & Feasibility) — completed
- **Created:** 2026-03-05

---

## Motivation

Task 001 audited all available Thai romanization sources and found that **no existing source produces informal romanization patterns** — the way Thai people actually romanize words in casual contexts (chat messages, social media, karaoke-style typing). Every programmatic source (TLTK, PyThaiNLP, thpronun, thai2rom-dataset) produces formal RTGS-like output.

The gap is significant. For example, the common greeting สวัสดี is romanized as `sawatdi` by RTGS-based engines, but Thai users would typically type `sawatdee` or `sawasdee`. The word ดี (good) produces `di` formally, but users type `dee`. The word หมู (pork) produces `mu`, but users type `moo`.

Task 001 identified this as the "highest-impact future research task" and proposed a rule-based approach: take the formal RTGS-like romanization from TLTK (the best-performing engine at 98.75% accuracy) and apply systematic transformations to generate plausible informal variants.

This task designs, implements, and evaluates that variant generator.

---

## Research Questions

### Primary Questions

1. **What are the systematic patterns that distinguish informal Thai romanization from RTGS?** Catalog the specific transformations Thai users make when romanizing casually. Task 001 identified three initial categories (vowel doubling, final consonant softening, simplified consonant clusters), but the full set of patterns needs to be documented with examples.

2. **Can we build a rule-based variant generator that produces realistic informal romanizations from TLTK's formal output?** Implement a generator, apply it to the 80-word test set from Task 001, and evaluate whether the output looks like plausible informal romanization.

3. **How many variants per word does this approach produce, and is the count manageable for trie construction?** The trie needs to stay within reasonable memory bounds. If the generator produces 50 variants per word, that's different from 5. Measure the expansion factor and assess whether pruning is needed.

4. **What is the quality of the generated variants?** For each word in the test set, do the generated variants include forms that a Thai user would plausibly type? Are there many false variants (forms no one would type)? A high false-variant rate would pollute the trie with useless entries.

### Secondary Question

5. **Can we produce a seed benchmark dataset from this work?** Combine the 80-word test set, the TLTK base romanizations, and the generated variants into a structured dataset of `(Thai word, [acceptable romanizations])` pairs. This becomes the foundation for the word conversion benchmark that future tasks test against.

---

## Known Transformation Patterns (from Task 001)

These are starting points, not an exhaustive list. The agent should investigate and extend these.

### Vowel Lengthening / Doubling
Thai long vowels are often represented by doubling in informal romanization:
- `i` → `ee` (ดี: `di` → `dee`)
- `u` → `oo` (หมู: `mu` → `moo`)
- `a` → `aa` (in some contexts)
- `o` → `oh` or `oo` (depending on the Thai vowel)

The challenge: this must be sensitive to whether the Thai vowel is actually long. Doubling a short vowel would produce an incorrect variant. TLTK's syllable-level output or thpronun's syllable-aligned data may help distinguish long from short vowels.

### Final Consonant Softening
Thai final consonants often get voiced in informal romanization:
- Final `t` → `d` (สวัสดี: `sawat` → `sawad`)
- Final `p` → `b`
- Final `k` → `g` (less common)

### Consonant Cluster Simplification
Formal romanization preserves aspirated/unaspirated distinctions that casual typers often drop:
- `kh` → `k` (ครับ: `khrap` → `krap` or `krab`)
- `th` → `t` (ไทย: `thai` → `tai`)
- `ph` → `p` (but not always — "pho" as in ผัดไท is common)

### Other Patterns to Investigate
- Tone mark omission (RTGS doesn't include tones, but some systems do)
- `r` dropping (a very common feature of spoken Thai — กรุงเทพ may be romanized as `krungthep` or `kungthep`)
- `l`/`r` interchange (reflects Thai dialectal variation)
- Final `-n` vs `-ng` handling
- Common word-specific spellings that don't follow any systematic rule (e.g., "pad thai" for ผัดไท)

---

## Constraints

- **Language:** Python. Notebooks for exploration, reusable code in `src/` if the variant generator is substantial enough to be a module.
- **Input dependency:** Use TLTK's `th2roman()` output as the primary base romanization. The agent should have access to Task 001's experiment artifacts in `experiments/001-romanization-source-audit/` for the 80-word test set and existing romanization outputs. (Note: The research branch is not merged into main, and you must checkout / clone it separately to view its full contents)
- **Evaluation is qualitative but structured.** For each word in the test set, list the generated variants and manually assess: (a) does the set include at least one form a Thai user would plausibly type? (b) how many of the generated variants are implausible? Express this as coverage rate and noise rate across the test set.
- **Syllable awareness is important.** Many transformations apply at the syllable level, not the whole-word level. If the agent can leverage TLTK's syllable segmentation or thpronun's syllable-aligned output, that will produce better variants than naive string replacement.
- **The variant generator should be deterministic and configurable.** Given the same input and configuration, it should produce the same output. Transformation rules should be toggleable so we can later evaluate which rules help and which add noise.

---

## Expected Deliverables

### Primary Deliverables

1. **Research summary** (`research/002-informal-romanization-variants/summary.md`) containing:
   - Documented catalog of informal romanization transformation patterns, with Thai examples
   - Description of the variant generator's design (what rules it applies, in what order)
   - Evaluation results: coverage rate, noise rate, expansion factor across the test set
   - Analysis of which transformation patterns are highest-value (high coverage, low noise) vs problematic (high noise)
   - Recommendations for which rules to include in production trie construction

2. **Variant generator code** (`experiments/002-informal-romanization-variants/`) containing:
   - The variant generator implementation (should be importable and reusable)
   - Evaluation notebook showing the generator's output on the full test set
   - Configuration showing which rules are active

### Secondary Deliverable

3. **Seed benchmark dataset** (`benchmarks/word-conversion/seed-benchmark.json` or similar) containing:
   - Structured entries of the form: `{ "thai": "สวัสดี", "accepted_romanizations": ["sawatdi", "sawatdee", "sawasdee", ...], "source": "task-002-generated" }`
   - Built from the 80-word test set, combining TLTK base romanizations with the curated (noise-filtered) generated variants
   - Include a README explaining the format, how entries were generated, and known limitations
   - This dataset should be treated as a **draft** — it will be reviewed and refined by the project maintainer before becoming an official benchmark

---

## Context Documents

The agent should read these for full context:

- `docs/research-workflow.md` — Research process and conventions
- `research/001-romanization-source-audit/summary.md` — Task 001 findings (the foundation this task builds on)
- Experiments from Task 001 in `experiments/001-romanization-source-audit/` — existing code, test word set, romanization outputs
- The conversion algorithm design document describes how romanization variants feed into the trie with source confidence weights. Variants generated by this task would receive lower confidence weights than the primary TLTK romanization.

---

## Notes for the Agent

- **Start by reading Task 001's summary and experiment artifacts thoroughly.** This task is a direct continuation — don't redo work that's already been done.
- **The 80-word test set from Task 001 is your primary evaluation set.** Use it as-is rather than creating a new one. If you need to extend it for specific edge cases, add to it but keep the original 80 intact for comparability.
- **Prioritize precision over recall in the variant generator.** A variant that no Thai person would type is worse than a missing variant. It's better to generate 3 plausible variants per word than 15 variants where 10 are garbage. The trie can always be expanded later; removing bad entries is harder.
- **Think about this from the user's perspective.** When a Thai person types a romanized word quickly in a chat, what shortcuts do they take? They don't think about RTGS rules — they write something that sounds right to them. That intuitive "sounds right" is what the variants should capture.
- **The seed benchmark is a secondary deliverable, not a distraction.** If generating it is straightforward from the evaluation work, include it. If it requires significant additional effort, note it as future work.
- **For the GitHub Agents environment:** This task should be executable with standard Python packages (PyThaiNLP, TLTK, standard library). It does not require PyTorch, C++ compilation, or web scraping. If you need thpronun's syllable data, check if Task 001's experiments already include cached output from it.
