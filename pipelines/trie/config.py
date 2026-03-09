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
# Variant generator settings
# ---------------------------------------------------------------------------

MAX_VARIANTS_PER_WORD = 100  # Match benchmark generation setting

# ---------------------------------------------------------------------------
# Processing settings
# ---------------------------------------------------------------------------

# Number of worker processes for variant generation (0 = sequential).
# Keep low to avoid OOM in memory-constrained environments (devcontainers).
# Each forked worker carries a full copy of the TLTK runtime.
NUM_WORKERS = 2

# Progress logging interval (every N words)
LOG_INTERVAL = 1000
