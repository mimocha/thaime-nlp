"""Shared paths and constants for n-gram extraction pipeline."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_DATA_DIR = REPO_ROOT / "data" / "corpora" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"

TRIE_DATASET_PATH = REPO_ROOT / "pipelines" / "trie" / "outputs" / "trie_dataset.json"

# ---------------------------------------------------------------------------
# Corpus sources (no pythainlp — it has no text to tokenize)
# ---------------------------------------------------------------------------

CORPORA = ["wisesight", "wongnai", "prachathai", "thwiki"]

# ---------------------------------------------------------------------------
# Processing settings
# ---------------------------------------------------------------------------

NUM_WORKERS = 8
CHUNK_SIZE = 100
