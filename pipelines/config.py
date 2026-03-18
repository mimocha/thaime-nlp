"""Consolidated configuration for all pipelines.

Provides shared constants (paths, corpora list) and per-pipeline config
classes (``TrieConfig``, ``NgramConfig``, ``BenchmarkConfig``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.utils.versioning import resolve_latest_version

# ---------------------------------------------------------------------------
# Shared paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
RAW_DATA_DIR = REPO_ROOT / "data" / "corpora" / "raw"

# ---------------------------------------------------------------------------
# Corpus sources
# ---------------------------------------------------------------------------

# All sources (trie pipeline uses all, including pythainlp dictionary)
ALL_SOURCES: dict[str, bool] = {
    "wisesight": True,
    "wongnai": True,
    "prachathai": True,
    "thwiki": True,
    "pythainlp": True,
}

# Text-only corpora (ngram pipeline — pythainlp has no text to tokenize)
TEXT_CORPORA: list[str] = ["wisesight", "wongnai", "prachathai", "thwiki"]


# ---------------------------------------------------------------------------
# Per-pipeline configuration
# ---------------------------------------------------------------------------


@dataclass
class TrieConfig:
    """Configuration for the trie generation pipeline."""

    # Word list sources
    sources: dict[str, bool] = field(default_factory=lambda: dict(ALL_SOURCES))

    # Manual overrides directory
    overrides_dir: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "dictionaries" / "word_overrides"
    )

    # Word exclusion list directory
    exclusions_dir: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "dictionaries" / "word_exclusions"
    )

    # Dataset filters
    min_source_count: int = 2
    min_frequency: float = 5e-6
    vocab_limit: int = 0  # 0 = no limit
    max_length_ratio: float = 2.0

    # Variant generator settings
    max_variants_per_word: int = 100

    # Processing settings
    num_workers: int = 12
    log_interval: int = 1000
    tokenize_chunk_size: int = 500

    # Output paths
    output_dir: Path = field(default_factory=lambda: OUTPUT_DIR)

    @property
    def wordlist_dir(self) -> Path:
        return self.output_dir / "wordlist"

    @property
    def variants_dir(self) -> Path:
        return self.output_dir / "variants"

    @property
    def trie_dir(self) -> Path:
        return self.output_dir / "trie"

    def get_overrides_path(self) -> Path:
        """Resolve the latest overrides file by semantic version."""
        return resolve_latest_version(self.overrides_dir, "overrides-v*.yaml")

    def get_exclusions_path(self) -> Path:
        """Resolve the latest exclusions file by semantic version."""
        return resolve_latest_version(self.exclusions_dir, "exclusions-v*.txt")


@dataclass
class NgramConfig:
    """Configuration for the n-gram generation pipeline."""

    corpora: list[str] = field(default_factory=lambda: list(TEXT_CORPORA))

    # Processing settings
    num_workers: int = 12
    chunk_size: int = 100
    log_interval: int = 10000

    # Encode settings (Stage 4)
    encode_min_count: int = 15
    encode_min_source_count: int = 2
    encode_min_frequency: float = 5e-6
    encode_alpha: float = 0.4
    encode_smoothing: str = "sbo"

    # Output paths
    output_dir: Path = field(default_factory=lambda: OUTPUT_DIR)

    @property
    def tokens_dir(self) -> Path:
        return self.output_dir / "tokens"

    @property
    def ngram_dir(self) -> Path:
        return self.output_dir / "ngram"

    @property
    def encode_dir(self) -> Path:
        return self.output_dir / "ngram"

    @property
    def trie_dataset_path(self) -> Path:
        return self.output_dir / "trie" / "trie_dataset.json"


@dataclass
class BenchmarkConfig:
    """Configuration for the benchmark word-conversion pipeline."""

    # Corpora used for frequency extraction (no thwiki — too noisy for benchmarks)
    corpora: list[str] = field(
        default_factory=lambda: ["wisesight", "wongnai", "prachathai"]
    )

    # Processing settings
    top_k: int = 500
    max_variants: int = 100
    num_workers: int = 2

    # Output paths
    output_dir: Path = field(default_factory=lambda: OUTPUT_DIR)

    @property
    def benchmark_dir(self) -> Path:
        return self.output_dir / "benchmarks" / "word_conversion"


@dataclass
class LlmFilterConfig:
    """Configuration for the LLM vocabulary filter."""

    # Input
    wordlist_path: Path = field(
        default_factory=lambda: OUTPUT_DIR / "wordlist" / "wordlist.csv"
    )

    # Output
    output_dir: Path = field(default_factory=lambda: OUTPUT_DIR / "llm_filter")

    # Exclusion list destination (versioned data directory)
    exclusions_dir: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "dictionaries" / "word_exclusions"
    )

    # LLM settings
    model_id: str = "global.anthropic.claude-sonnet-4-6"
    region: str = "us-east-1"

    # Processing settings
    batch_size: int = 1000
    wordlist_limit: int = 5000
    num_workers: int = 4
