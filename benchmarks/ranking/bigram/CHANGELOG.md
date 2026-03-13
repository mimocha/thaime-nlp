# Changelog — Ranking Benchmark (Bigram)

## v0.1.0 (2026-03-13)

Initial benchmark created as part of Research 007 (N-gram Transition Probability).

- 200 total entries
  - 17 no-context baselines across 17 romanization families
  - 183 context-dependent cases across 13 romanization families
  - 9 repeater (ๆ) cases tagged `[repeater]` for future IME work
- Romanization families: kao, mai, kan, tai, kai, chao, tang, pa, kum, pag, tae, cha, toh
- Context words validated by native Thai speaker
- Collision analysis source: `pipelines/trie/outputs/trie_dataset.json` (15K vocab)
