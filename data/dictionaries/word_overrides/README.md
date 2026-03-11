# Word Overrides

Human-curated romanization overrides for the trie generation pipeline. Words
listed here are merged into the trie dataset after variant generation, bypassing
both the word filter and the variant generator.

## Use Cases

- Legitimate words that TLTK cannot romanize (colloquial particles, slang)
- Words filtered out by aggressive statistical rules but still valid
- Loanwords with non-standard romanization
- Words not found in any corpus but important for input method coverage

## File Format

YAML dictionary mapping Thai words to lists of romanization variants:

```yaml
กุ้ง:
  - koong
  - kung

เซลฟี่:
  - selfie
  - selfi
```

## Pipeline Integration

Override words:
- Are appended to the vocabulary regardless of source/frequency filters
- Have their romanizations used as-is (no variant generation)
- Are exempt from vocabulary truncation limits
- Are exempt from the LLM exclusion list

## Versioning

Files use semantic versioning: `overrides-v{major}.{minor}.{patch}.yaml`.
