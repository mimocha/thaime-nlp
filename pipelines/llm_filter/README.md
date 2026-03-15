# LLM Vocabulary Filter Pipeline

Offline, maintainer-only tool that uses AWS Bedrock (Claude Sonnet) to
semantically evaluate whether tokens in the wordlist are real Thai words.
Produces candidate exclusions for human review.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- `boto3` installed (`uv pip install boto3`)
- A wordlist from the trie pipeline (`pipelines/outputs/wordlist/wordlist.csv`)

## Workflow

### 1. Generate raw exclusion list

```bash
python -m pipelines llm-filter generate
python -m pipelines llm-filter generate --batch-size 500 --limit 3000
```

This sends batches of words to Claude for review and writes:
- `pipelines/outputs/llm_filter/dropped_words_raw.txt` — candidate exclusions
- `pipelines/outputs/llm_filter/llm_filter.log` — raw LLM responses

### 2. Review

Manually inspect `dropped_words_raw.txt` and remove any legitimate words
that were incorrectly flagged.

### 3. Approve

```bash
python -m pipelines llm-filter approve --version 0.5.0
```

Copies the reviewed list to `data/dictionaries/word_exclusions/exclusions-v0.5.0.txt`,
which the trie pipeline reads during its export stage.

## Inputs / Outputs

| File | Description |
|------|-------------|
| `pipelines/outputs/wordlist/wordlist.csv` | Input wordlist (from `python -m pipelines trie wordlist`) |
| `pipelines/outputs/llm_filter/dropped_words_raw.txt` | Raw exclusion candidates |
| `pipelines/outputs/llm_filter/llm_filter.log` | LLM response log |
| `data/dictionaries/word_exclusions/exclusions-v*.txt` | Approved exclusion list (versioned) |

## Configuration

All defaults are in `LlmFilterConfig` (`pipelines/config.py`). CLI flags override them.

| Setting | Default | Description |
|---------|---------|-------------|
| `wordlist_path` | `pipelines/outputs/wordlist/wordlist.csv` | Input wordlist |
| `model_id` | `global.anthropic.claude-sonnet-4-6` | Bedrock model |
| `region` | `us-east-1` | AWS region |
| `batch_size` | 1000 | Words per LLM call |
| `wordlist_limit` | 5000 | Max words to process |
| `num_workers` | 4 | Concurrent API calls |
