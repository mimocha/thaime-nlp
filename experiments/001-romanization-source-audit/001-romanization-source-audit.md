# Research Task 001: Thai Romanization Source Audit & Feasibility

## Metadata

- **Task ID:** 001
- **Topic:** Romanization data sources for Latin-to-Thai trie construction
- **Branch:** `research/001-romanization-source-audit`
- **Status:** Proposed
- **Dependencies:** None (foundational task)
- **Created:** 2026-03-04

---

## Motivation

THAIME's core data structure is a trie that maps Latin (romanized) character sequences to Thai words. The quality of this trie — how many romanization forms per word, and how well they cover real user typing patterns — is the single biggest factor in how usable the IME feels.

There is no single canonical source for Latin-to-Thai romanization pairs. Instead, we expect to combine multiple sources of varying quality and coverage. Before we can build the trie or design a weighting scheme, we need a clear picture of what sources exist, what each one actually produces, and whether each is practically usable.

This task is the foundational audit that all subsequent romanization work depends on.

---

## Research Questions

### Primary Questions

1. **What romanization sources exist for Thai?** Audit all viable sources for generating Latin-to-Thai word mappings. We have identified three starting candidates (see below), but there may be others. Cast a wide net — consider academic tools, government resources, existing Thai NLP libraries beyond PyThaiNLP, online dictionaries, transliteration APIs, and community-built datasets.

2. **For each source: what does it actually produce, and is it usable?** Evaluate each source on:
   - **Output format & quality:** What does the romanization look like? Is it consistent? Does it reflect how real people type, or is it purely formal/academic?
   - **Coverage:** How many Thai words can it romanize? Does it handle common vocabulary well? Does it cover colloquial/slang Thai or only formal language?
   - **Accessibility:** Can we programmatically generate romanizations at scale? What are the dependencies, costs, and reliability?
   - **Licensing:** Can we legally use the output in an MPL 2.0 licensed project? Are there attribution requirements?
   - **Failure modes:** Where does each source break down? What types of words or constructions does it handle poorly?

3. **How do the sources compare to each other?** For a sample of Thai words, generate romanizations from each source and compare. Where do they agree? Where do they diverge? Which source's output most closely matches how a Thai person would informally romanize the word (i.e., the "karaoke test")?

### Secondary Questions

4. **Are there sources we haven't considered?** Specifically investigate:
   - Thai-English dictionaries that include pronunciation guides (e.g., Longdo Dictionary API, thai-language.com structured data)
   - IPA-based intermediate representations (Thai → IPA → Latin) via tools like TLTK's grapheme-to-phoneme
   - Wiktionary structured data for Thai entries
   - Any academic datasets from Thai NLP research on transliteration
   - Existing romanization in Thai Wikipedia (article names, redirects)
   - Social media / messaging data patterns (how do Thai users actually romanize in LINE, Twitter, etc.?)

5. **What are the characteristics of "informal Thai romanization" as actually practiced?** This is the target we're trying to approximate. Understanding the patterns (e.g., silent letters dropped, tones ignored, vowel simplification) will help evaluate which sources are closest to real usage.

---

## Known Sources to Evaluate

### 1. RTGS via PyThaiNLP

**What it is:** The Royal Thai General System of Transcription, available programmatically through PyThaiNLP's `romanize()` function and potentially TLTK's `th2roman()`.

**What we know:** Rule-based, deterministic, highest formal confidence. Produces a single canonical romanization per word. May feel "stiff" compared to how people actually type.

**Investigate:** Compare PyThaiNLP's RTGS output with TLTK's romanization. Are there other romanization modes in these libraries beyond RTGS? (PyThaiNLP has multiple romanization engines — `thai2rom`, `royin`, etc.) Document what each mode produces and how they differ.

### 2. Soundex / Metaphone (Phonetic Algorithms)

**What it is:** Algorithms that generate phonetic hash codes, allowing words that sound similar to match. PyThaiNLP provides Thai-specific Soundex implementations. The idea is to use these to expand romanization coverage — if two Latin strings map to the same phonetic code, they could match the same Thai word.

**What we know:** This is not a romanization source per se, but a fuzziness mechanism. It could be used to generate additional romanization variants from existing ones.

**Investigate:** How well do Thai Soundex/Metaphone implementations work in practice? What is the collision rate (false positive rate) — do unrelated words map to the same code too often? Is this better applied as a pre-computed expansion at trie build time, or as a runtime fallback? What specific implementations exist in PyThaiNLP and elsewhere?

### 3. Karaoke Transliteration Data

**What it is:** Online tools and datasets that provide English-phonetic readings of Thai text, originally designed for karaoke singers who can't read Thai script. Sources include thai-language.com, dekgenius.com karaoke generator, and thai2english.com.

**What we know:** This may be the closest approximation to "how people actually romanize Thai" since it's designed to be read aloud by non-Thai readers. However, quality, coverage, and accessibility vary.

**Investigate:** For each karaoke source: Can we programmatically access the data (API, scraping feasibility, downloadable datasets)? What does the romanization scheme look like — is it consistent within a source? What's the vocabulary coverage? Are there licensing/terms-of-service concerns? How does the romanization compare to RTGS and to informal Thai romanization?

---

## Constraints

- **Language:** Python. Use Jupyter notebooks for exploratory work, Python scripts for any reusable utilities.
- **Key libraries:** PyThaiNLP and TLTK are the primary Thai NLP tools. Install and evaluate both.
- **No benchmark required for this task.** Qualitative assessment with concrete examples is sufficient. Pick a representative sample of ~50-100 Thai words spanning common vocabulary (greetings, food, places, verbs, slang) and use them as a consistent comparison set across sources.
- **Document everything.** Each source should have clear documentation of what it produces, with examples. Someone reading the summary should be able to decide whether to invest further effort in that source.
- **Legal caution with web scraping.** Note terms of service for any web sources. Do not scrape at scale during this audit — small samples for evaluation are fine.

---

## Expected Deliverables

1. **Research summary** (`research/001-romanization-source-audit/summary.md`) containing:
   - A catalog of all romanization sources found, with assessment of each
   - Side-by-side comparison of outputs for the sample word set
   - Recommendations on which sources to pursue for trie construction
   - Identified gaps — what romanization patterns are not covered by any source
   - Any new sources discovered beyond the three starting candidates

2. **Working code** (`experiments/001-romanization-source-audit/`) containing:
   - Notebooks or scripts demonstrating each source's output
   - The sample word set used for comparison
   - Any utility functions written for accessing the sources

---

## Context Documents

The agent should read these documents for full project context:

- `docs/research-workflow.md` — How to conduct research in this repo
- Project context files (provided in CLAUDE.md)
- The conversion algorithm document describes how romanization data feeds into the trie: multiple romanization keys per Thai word, each with a source confidence weight. This task informs what those sources and weights should be.

---

## Notes for the Agent

- This is a **survey and feasibility** task, not a trie-building task. The goal is to map the landscape and identify what's viable, not to produce a final dataset.
- Be thorough in investigating PyThaiNLP and TLTK — they have more functionality than their README suggests. Dig into the actual API docs and source code.
- When evaluating "how close to real informal romanization" a source is, think about how a Thai person would type the word in a LINE chat message to a friend. That's the target behavior THAIME is trying to support.
- If you discover a source that seems promising but requires significant engineering effort to access, document it clearly as a lead for future work rather than trying to fully implement access.
- For karaoke sources, pay special attention to whether the romanization is syllable-aligned (each Thai syllable maps to a Latin chunk) or word-level. Syllable alignment would be significantly more valuable for trie construction.
