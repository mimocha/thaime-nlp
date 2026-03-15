# Word Exclusions

LLM-generated exclusion lists for the trie generation pipeline. Words in these
lists are filtered out of the vocabulary before variant generation.

## Workflow

1. Run the LLM filter to generate a raw exclusion list:
   ```
   python -m pipelines llm-filter generate
   ```

2. Review the raw output at `pipelines/outputs/llm_filter/dropped_words_raw.txt`.
   Remove any legitimate words that were incorrectly flagged.

3. Approve the reviewed list:
   ```
   python -m pipelines llm-filter approve --version 1.0.0
   ```

4. Use in the pipeline:
   ```
   python -m pipelines.trie.generate --exclusion-list data/dictionaries/word_exclusions/exclusions-v1.0.0.txt
   ```

## File Format

Plain text, one Thai word per line, sorted alphabetically. Lines starting with
`#` are ignored.

## Versioning

Files use semantic versioning: `exclusions-v{major}.{minor}.{patch}.txt`.

- **Major**: Full re-generation with a different model or prompt.
- **Minor**: Re-generation on updated wordlist or with tuned parameters.
- **Patch**: Manual corrections to an existing list.
