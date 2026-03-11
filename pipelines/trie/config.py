"""Configuration for the trie generation pipeline."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
RAW_DATA_DIR = REPO_ROOT / "data" / "corpora" / "raw"

# ---------------------------------------------------------------------------
# Word list sources — all enabled by default
# ---------------------------------------------------------------------------

SOURCES: dict[str, bool] = {
    "wisesight": True,
    "wongnai": True,
    "prachathai": True,
    "thwiki": True,
    "pythainlp": True,
}

# ---------------------------------------------------------------------------
# Manual overrides — romanizations for words TLTK can't handle
# ---------------------------------------------------------------------------

OVERRIDES_PATH = REPO_ROOT / "data" / "dictionaries" / "word_overrides" / "overrides-v0.4.2.yaml"

# ---------------------------------------------------------------------------
# Word exclusion list — LLM-generated list of words to drop
# ---------------------------------------------------------------------------

# Path to the approved exclusion list. Set to None to disable.
# Generate with: python -m pipelines.trie.llm_filter generate
EXCLUSIONS_PATH = REPO_ROOT / "data" / "dictionaries" / "word_exclusions" / "exclusions-v0.4.2.txt"

# ---------------------------------------------------------------------------
# Dataset filters — applied after variant generation and overrides
# ---------------------------------------------------------------------------

# Minimum number of corpus sources a word must appear in.
# Words from pythainlp (curated dictionary) are exempt from this rule.
MIN_SOURCE_COUNT = 2

# Minimum word frequency (after cross-source normalization).
MIN_FREQUENCY = 5e-6

# Vocabulary size limit — after all filters, keep the top N words by
# frequency. 0 means no limit (keep all words that pass filters).
VOCAB_LIMIT = 0

# Romanization length-ratio threshold for sanity check.
# Words where (thai_base_len / min_romanization_len) exceeds this ratio
# are flagged as likely TLTK partial-romanization failures and removed.
# Override words are exempt from this check.
MAX_LENGTH_RATIO = 2.0

# ---------------------------------------------------------------------------
# Variant generator settings
# ---------------------------------------------------------------------------

MAX_VARIANTS_PER_WORD = 100  # Match benchmark generation setting

# ---------------------------------------------------------------------------
# Processing settings
# ---------------------------------------------------------------------------

# Number of worker processes for variant generation (0 = sequential).
# Keep low to avoid OOM in memory-constrained environments (devcontainers).
# Each forked worker carries a full copy of the TLTK runtime.
NUM_WORKERS = 8

# Progress logging interval (every N words)
LOG_INTERVAL = 1000
