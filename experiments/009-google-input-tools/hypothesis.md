# Google Input Tools Thai: Background Research & Hypothesis

**Topic:** research/009-google-input-tools
**Date:** 2026-07-12
**Author:** Chawit Leosrisook (maintainer) + Claude (agent)

## Problem Statement

Google Input Tools ships the only other known production Latin-to-Thai transliteration
IME. It is a mature reference implementation with full-sentence lattice conversion,
single-word fallbacks, and a backend API that is still operational. THAIME currently has
no external quality yardstick: our accuracy numbers are self-referential, measured only
against our own benchmarks — and R007 flagged **Benchmark Reliability** as a High-priority
open problem (the bigram ranking benchmark had roughly 55 effective discriminating rows and
~20% compound-tokenization contamination).

The question this topic answers: **how does THAIME's conversion quality compare to a
production reference (Google), and where — segmentation, ranking, vocabulary, or
romanization coverage — does THAIME lose?** Localizing the gap turns "our benchmark says
X%" into "against a real system we are behind by Y on category Z," which is directly
actionable and gives the Benchmark Reliability topic an external anchor. A secondary
byproduct: Google-accepted romanization variants that THAIME does not generate are
candidates for the component dictionary.

## Background Research

### Google Input Tools Thai transliteration IME

Google launched a Thai transliteration IME in May 2016 (blog post "Pim Thai Dai Laew"),
distributed as a Chrome extension (`mclkkofklkfljcocdinagocijmpgbhab`) and embedded in
Gmail and Google Drive. It never gained significant traction, likely because it was gated
behind a Chrome extension, but the implementation itself is production-quality:

- **Candidate #1** is a full-sentence lattice conversion of the whole Latin input.
- **Candidates #2–5** are single-word alternatives for the first word, with pagination.
- **Candidate #6** is a Latin pass-through (leave the input untransliterated).

Source: https://blog.google/company-news/inside-google/around-the-globe/google-asia/pim-thai-dai-laew-you-can-now-type-in/

### The inputtools.google.com backend API

The extension talks to `https://inputtools.google.com/request`, an undocumented endpoint
that outlived the public Google Transliteration API (deprecated 2011). The unofficial
`google-transliteration-api` Python package and community clients use the form
`request?text={input}&itc=th-t-i0&num={n}`, returning ranked Thai candidates. Because it
backs Google's own current products, it is expected to remain available — but this must be
validated empirically before any scaled use, and we treat it strictly as a benchmarking
snapshot, never a runtime dependency.

Source: https://pypi.org/project/google-transliteration-api/ ; https://github.com/KSubedi/transliteration-input-tools

### THAIME's current conversion approach (context)

THAIME uses a two-stage pipeline: (1) fuzzy prefix search over a multi-romanization trie
builds a word lattice, (2) Viterbi k-best with n-gram language-model scoring picks the best
path (see R004, R005). Recent work shifted strategy: the component romanization dictionary
(v0.5.0, 2026-03-15) **restored 37 previously-pruned variants** on the explicit reasoning
that "bigram/trigram Viterbi scoring now in the engine can disambiguate a larger candidate
set" — i.e. THAIME deliberately *widened* romanization coverage and moved the burden of
disambiguation onto the n-gram scorer (R007: Stupid Backoff, `bigram_weight=2.0`;
R008: binary delivery format). So the interesting question is no longer "does THAIME have
coverage holes" but "given wide coverage, does the scorer rank the right candidate as well
as a mature production system does."

### Preliminary observation

Maintainer testing of the live extension: `sawaddee` and `sawatdee` both convert to สวัสดี,
but `sawasdee` is rejected. This shows Google faces the same romanization-variant coverage
tradeoffs THAIME does, and that direct input-by-input comparison is meaningful.

### Relevance to THAIME

Google is the closest thing to a ground-truth production baseline for our exact task. A
head-to-head on a shared test set gives (a) an external calibration for our benchmarks,
(b) a category breakdown of where we lose, and (c) a stream of real romanization variants
to consider for the dictionary. The engine/frontend UX side of Google's implementation
(candidate presentation, pagination, partial commit) is also interesting but belongs to the
`thaime` engine/demo repo, not this data-focused research repo, so it is out of scope here.

## Hypothesis / Proposed Approach

**H1 (primary).** On a shared test set, Google's top-1 accuracy will exceed THAIME's,
driven mainly by *segmentation* and *ranking* on multi-word phrases (Google has far more
training data and a more mature LM), not by single-word transliteration — where THAIME's
Thai-tuned component generator should be competitive or better on informal variants.

**H2.** THAIME's disagreements with Google will concentrate into a small number of
categories (segmentation-penalty λ tuning, n-gram sparsity/ranking, vocabulary coverage),
so the comparison yields a short, prioritized list of improvements rather than diffuse
noise.

**H3 (secondary).** Mining Google-accepted romanizations for high-frequency Thai words will
surface tens of variants THAIME's rule-based generator does not produce, a fraction of which
the maintainer will judge natural enough to add to the component dictionary.

Proposed approach: validate the API as a hard go/no-go gate, then run both systems over a
shared, reliability-conscious test set, compute top-1/top-5/MRR, and categorize every
disagreement — with variant mining falling out of the same cached runs. Detailed procedure
in `plan.md`.

## Sources

- Google Blog, "Pim Thai Dai Laew" (2016-05-26) — https://blog.google/company-news/inside-google/around-the-globe/google-asia/pim-thai-dai-laew-you-can-now-type-in/
- Google Input Tools Chrome extension — https://chromewebstore.google.com/detail/google-input-tools/mclkkofklkfljcocdinagocijmpgbhab
- `google-transliteration-api` (unofficial) — https://pypi.org/project/google-transliteration-api/
- Community backend client — https://github.com/KSubedi/transliteration-input-tools
- Deprecated Google Transliterate API — https://developers.google.com/transliterate/
- THAIME R003 (component romanization) — `research/003-component-romanization/summary.md`
- THAIME R005 (candidate selection) — `research/005-candidate-selection/summary.md`
- THAIME R007 (bigram scoring; Benchmark Reliability escalation) — `research/007-bigram-scoring/summary.md`
- THAIME R008 (n-gram delivery) — `research/008-ngram-delivery/summary.md`
- Component dictionary changelog (v0.5.0 variant restoration) — `data/dictionaries/component-romanization/CHANGELOG.md`
