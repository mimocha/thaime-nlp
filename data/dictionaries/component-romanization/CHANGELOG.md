# v0.4.2 (2026-03-11): Directory restructuring
- Moved dictionary YAML to be under `data/dictionaries/component-romanization/dictionary-vX.X.X.yaml`
- Changelog now residing separately in this file

# v0.4.1 (2026-03-11): Split /t/ coda into /t/ and /s/ entries.
- New [t/s] coda entry (g2p: "s") for ส/ศ/ษ finals, detected from Thai text.
- Removed [s] from "t" coda — now only ["t", "d"].
- Parallels the existing จ→c coda split pattern.
- Requires corresponding _detect_sor_coda() in variant_generator.py.
Onsets (54 -> 53, 1 removed):
- w: removed [v]
Vowels (54 -> 50, 4 removed) - will rely on fuzzy trie matching to cover these:
- oo: removed [ou]
- ue: removed [eu]
- uee: removed [eu]
- oe: removed [eo]

# v0.4.0 (2026-03-11): Aggressive variant pruning to reduce combinatorial explosion.
Total variants: 151 -> 123 (28 removed, 19% reduction).
Mean variants/entry: 2.13 -> 1.73.
Onsets (57 -> 54, 3 removed):
- t: removed [dt] — Paiboon-style dt produces noise at scale
- p: removed [bp] — same rationale as t/dt
- tr: removed [dtr] — same rationale as t/dt
Vowels (78 -> 54, 24 removed):
- a: removed [ah]
- aa: removed [ah]
- ee: removed [e, eh] — short form ambiguous with เอะ
- ii: removed [i] — short form ambiguous with อิ
- u: removed [oo] — ambiguous with อู
- uu: removed [u] — ambiguous with อุ
- o (short): no change
- oo (long): no change
- O (เอาะ): removed [or, oa], added [oh]
- OO (ออ): removed [o, aw], kept [or, oh]
- ae/aae: removed [aae] — unable to disambiguate long/short in romanization
- ue/uee: removed [uee] — unable to disambiguate long/short in romanization
- oe: removed [eo], added [uh]
- oee: removed [eo, uh], kept [oe, er, ur]
- ai: removed [aai, aii]
- ao: removed [aao, au, aw]
- ia: removed [ea]
- iao: removed [iaw, iew]
- ua: removed [uaa]
- uea: removed [ueaa]
Codas (16 -> 15, 1 net removed):
- c (จ coda): removed [t, d] — only keep [j] to avoid noise
- t: added [s] — cannot disambiguate ด/ต/ศ/ส etc. due to TLTK mapping all to /t/
Other changes:
- Added thai field to all vowel and coda entries for reference
- Cleaned up notes (removed redundant thai/g2p references)
- Reordered kl/khl/kw/khw entries for consistency with other cluster pairs
- Updated thr thai field to include ทร/ถร alongside ธร

# v0.3.1 (2026-03-09): Replaced "dr" onset variant with "dtr" (ตร cluster).
- "dtr" added to match Paiboon-like systems
"dr" was a holdover from an earlier iteration and was removed to match ต onset

# v0.3.0 (2026-03-09): 10K scale-up validation (Change Plan 04, commit 5).
- Added 4 onset clusters found in 10K vocabulary: khl (ขล/คล), phl (พล/ผล),
bl (บล), thr (ธร). Covers 130 previously-unknown onset occurrences.
- Removed "d" from ต onset (produces noise at scale; "dt" kept for disambiguation).
- Dictionary coverage on 10K vocabulary: 99.1% → ~99.9% after additions.

# v0.2.3 (2026-03-08): Second review-driven cleanup (Change Plan 04, commit 4 iteration).
- Added "uay" to uaj (อวย) diphthong (ด้วย->duay natural).
- Removed "ur" from UU (อื) vowel (produces unnatural forms: kur, rur, purntii).

# v0.2.2 (2026-03-08): Review-driven cleanup (Change Plan 04, commit 4 iteration).
- Removed "ua" from UUa (เอือ) vowel variants (ambiguous with อัว, produces nonsense).
- Removed "b" from ป onset, "bl" from ปล, "br" from ปร (produces nonsense romanizations).

# v0.2.1 (2026-03-07): Validation-driven variant refinements (Change Plan 04, commit 3).
- Added "oo" variant to short u vowel.
- Added "oh" to short o, "oa" to short O, "ou" to long uu.
- Added "ae" to long ee, "ow"/"aow"/"au" to ao diphthong.
- Added "iia" to ia, "ueaa" to uea, "eao"/"eaw" to iao diphthongs.
- Removed "aa"→"u" (invalid for long vowel; only valid for short a in closed syllables).
- Removed all j→y coda/diphthong variants (ai→ay, oi→oy, uai→uay, coda j→y).
- Removed "j" from ch onset (ช/ฉ; only valid for จ).
- Removed "gr" from khr onset (no benchmark evidence).
- Fixed hor-nam (หน/หม) detection to skip leading vowels.
- Fixed จ-as-coda detection (TLTK maps to 't'; now correctly uses 'c' coda entry).

# v0.2.0 (2026-03-07): Re-keyed from RTGS to TLTK g2p strings.
- Split RTGS "ch" into g2p "c" (จ) and "ch" (ช/ฉ/ฌ) with distinct variants.
- Split RTGS "o" vowel into g2p "O" (ออ) and "o" (โอ) with distinct variants.
- Added "c" coda entry for จ-as-coda (distinct from "t" coda).
- Added "nh" and "mh" onset entries for หน/หม words.

# v0.1.0 (2026-03-06): Initial version with RTGS keys (from Research 003).