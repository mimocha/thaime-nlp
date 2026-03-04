# Informal Thai Romanization Variant Generation: Background Research & Hypothesis

**Topic:** research/002-informal-romanization-variants
**Date:** 2026-03-04
**Author:** Claude (agent)

## Problem Statement

Can we build a rule-based generator that takes TLTK's formal RTGS-like Thai romanization and produces plausible informal romanization variants — the way Thai users actually type in chat, social media, and casual contexts? This is the highest-priority gap identified by Task 001's romanization source audit.

## Background Research

### RTGS vs Informal Romanization

The Royal Thai General System of Transcription (RTGS) is Thailand's official romanization standard. It produces systematic, unambiguous output (e.g., สวัสดี → "sawatdi", ดี → "di", หมู → "mu"). However, Thai users rarely type RTGS when romanizing casually. They use informal patterns that better reflect perceived pronunciation:

- **Vowel lengthening:** Thai distinguishes short and long vowels phonemically. RTGS collapses some long vowels to single letters (ดี → "di"), but informal romanization doubles them to indicate length: "dee", "dii". Similarly หมู → "moo" (not "mu").

- **Final consonant softening:** Thai final stops are unreleased (no audible release burst), making them sound voiced to English speakers. Informal romanization often voices them: ครับ → "krab" (not "khrap"), สวัสดี → "sawaddee" (not "sawatdi").

- **Consonant cluster simplification:** RTGS preserves aspiration distinctions (kh/k, th/t, ph/p) using digraphs. Casual typers often drop the 'h': ไทย → "tai" (not "thai"), ครับ → "krap" (not "khrap").

- **R-dropping:** A widespread feature of Bangkok Thai pronunciation. The /r/ sound is frequently dropped or replaced with /l/ in speech, and this carries over to typing: กรุงเทพ → "kungthep" (not "krungthep").

- **Initial voicing:** The Thai letter ก represents an unaspirated /k/ that sounds like English /g/ to native English speakers. Informal romanization often uses 'g': กิน → "gin" (not "kin"), ไก่ → "gai" (not "kai").

### Task 001 Findings

Task 001 audited all available Thai romanization sources and found that **no programmatic source produces informal patterns**. TLTK's `th2roman()` was identified as the best base source (98.75% accuracy on 80 test words) but outputs only RTGS-like forms. The audit recommended building a rule-based variant generator as the highest-impact next step.

### TLTK's Phonetic Analysis Capabilities

TLTK provides several useful features for syllable-aware variant generation:

- `th2ipa()` — IPA transcription with explicit long vowel marking (ː)
- `g2p()` — Phonemic transcription with doubled vowel letters for long vowels (e.g., "dii0" for ดี)
- `syl_segment()` — Thai syllable segmentation (สวัสดี → สวัส~ดี)

The g2p output uses `~` to separate groups that map 1:1 to Thai syllables, and `'` for sub-syllable parts. This provides the syllable-level phonetic information needed to apply transformations correctly (e.g., only doubling vowels that are actually long in Thai).

### Approach in Other IMEs

Input method engines for other languages (Chinese, Japanese, Korean) handle romanization variants differently — they typically work from a fixed romanization standard. Thai is unique because there is no single dominant romanization convention for casual use, and the variation is phonetically motivated rather than arbitrary.

## Hypothesis / Proposed Approach

A rule-based variant generator operating at the syllable level can produce realistic informal romanization variants from TLTK's formal output, with:

1. **High coverage** (>80% of common Thai words should have at least one plausible informal variant generated)
2. **Manageable expansion** (<10 variants per word on average, suitable for trie construction)
3. **Acceptable noise** (most generated variants should be plausible, not nonsensical)

The key design insight is that transformations should operate on decomposed syllable components (initial cluster, vowel nucleus, final consonant) and combine via Cartesian product. This enables cross-rule interactions (e.g., ph→p + u→oo + t→d yielding "pood" from "phut") that simple string replacement would miss.

## Sources

- Task 001 summary: `research/001-romanization-source-audit/summary.md`
- RTGS standard: https://en.wikipedia.org/wiki/Royal_Thai_General_System_of_Transcription
- TLTK documentation: https://pypi.org/project/tltk/
- Thai phonology: https://en.wikipedia.org/wiki/Thai_language#Phonology
