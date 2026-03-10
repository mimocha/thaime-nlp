"""Corpus registry — metadata for all available Thai NLP corpora.

Each corpus is described by a CorpusInfo dataclass containing its name,
description, license, source URLs, download method, and category.

The corpora were selected from the thaime-candidate research repo:
https://github.com/mimocha/thaime-candidate

Selected to cover formal writing, informal writing, and mixed web text:
- Prachathai 67K: Formal news articles
- Wisesight Sentiment: Informal social media
- Wongnai Reviews: Informal restaurant reviews
- Thai Wikipedia: Formal encyclopedia
- HSE Thai Corpus: Mixed web text (mostly news)
"""

from dataclasses import dataclass, field
from pathlib import Path

# Repo root is three levels up from this file (src/data/registry.py)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = REPO_ROOT / "data" / "corpora" / "raw"


@dataclass(frozen=True)
class CorpusInfo:
    """Metadata for a downloadable corpus."""

    name: str
    """Short identifier (used as directory name and CLI argument)."""

    description: str
    """Human-readable description of the corpus."""

    category: str
    """Content category: 'formal', 'informal', or 'mixed'."""

    license: str
    """License identifier (e.g. 'CC0-1.0', 'Apache-2.0')."""

    source_url: str
    """URL to the canonical source (GitHub repo, project page, etc.)."""

    download_urls: list[str] = field(default_factory=list)
    """Direct download URL(s). Multiple URLs for corpora split across files."""

    size_estimate: str = "unknown"
    """Approximate download size (e.g. '50 MB', '1.5 GB')."""

    notes: str = ""
    """Additional notes about download or usage."""

    def raw_dir(self) -> Path:
        """Return the local directory where raw data is stored."""
        return RAW_DATA_DIR / self.name


# ---------------------------------------------------------------------------
# Corpus Registry
# ---------------------------------------------------------------------------

CORPUS_REGISTRY: dict[str, CorpusInfo] = {}


def _register(corpus: CorpusInfo) -> CorpusInfo:
    """Register a corpus in the global registry."""
    CORPUS_REGISTRY[corpus.name] = corpus
    return corpus


# -- Prachathai 67K --------------------------------------------------------
_register(CorpusInfo(
    name="prachathai",
    description=(
        "Prachathai 67K — 67,889 news articles scraped from Prachathai.com, "
        "a left-leaning Thai news site. Formal news writing style."
    ),
    category="formal",
    license="Apache-2.0",
    source_url="https://github.com/PyThaiNLP/prachathai-67k",
    download_urls=[
        # The data.zip in the repo is Git LFS — use the GitHub Release asset instead
        "https://github.com/PyThaiNLP/prachathai-67k/releases/download/v1.1/data.zip",
    ],
    size_estimate="~242 MB",
    notes=(
        "Downloaded from the v1.1 GitHub Release (the repo copy is Git LFS "
        "and cannot be fetched via raw URL). Contains zipped JSONL files with "
        "article body text and topic tags. Also available on Hugging Face as "
        "'PyThaiNLP/prachathai67k'."
    ),
))

# -- Wisesight Sentiment ---------------------------------------------------
_register(CorpusInfo(
    name="wisesight",
    description=(
        "Wisesight Sentiment Corpus — 26,737 Thai social media messages "
        "with sentiment labels. Informal and conversational style."
    ),
    category="informal",
    license="CC0-1.0",
    source_url="https://github.com/PyThaiNLP/wisesight-sentiment",
    download_urls=[
        "https://raw.githubusercontent.com/PyThaiNLP/wisesight-sentiment/master/pos.txt",
        "https://raw.githubusercontent.com/PyThaiNLP/wisesight-sentiment/master/neg.txt",
        "https://raw.githubusercontent.com/PyThaiNLP/wisesight-sentiment/master/neu.txt",
        "https://raw.githubusercontent.com/PyThaiNLP/wisesight-sentiment/master/q.txt",
    ],
    size_estimate="~5 MB",
    notes=(
        "Four text files (pos/neg/neu/q), one message per line. "
        "All files are UTF-8 encoded. Combine all files for a complete corpus."
    ),
))

# -- Wongnai Reviews -------------------------------------------------------
_register(CorpusInfo(
    name="wongnai",
    description=(
        "Wongnai Corpus — Thai restaurant reviews with star ratings (1-5). "
        "Informal internet review style."
    ),
    category="informal",
    license="LGPL-3.0",
    source_url="https://github.com/wongnai/wongnai-corpus",
    download_urls=[
        "https://github.com/wongnai/wongnai-corpus/raw/master/review/review_dataset.zip",
    ],
    size_estimate="~60 MB",
    notes=(
        "The zip contains review text with star ratings. "
        "The dataset is also available through a Kaggle competition."
    ),
))

# -- Thai Wikipedia ---------------------------------------------------------
_register(CorpusInfo(
    name="thwiki",
    description=(
        "Thai Wikipedia — Complete dump of Thai-language Wikipedia articles. "
        "Formal encyclopedic writing style."
    ),
    category="formal",
    license="CC-BY-SA-3.0",
    source_url="https://dumps.wikimedia.org/thwiki/",
    download_urls=[
        "https://dumps.wikimedia.org/thwiki/latest/thwiki-latest-pages-articles.xml.bz2",
    ],
    size_estimate="~500 MB (compressed), ~1.5 GB (uncompressed)",
    notes=(
        "Large XML dump in MediaWiki format. Requires XML parsing to extract "
        "article text. Consider using the 'mwparserfromhell' or 'wikitextparser' "
        "library to clean wikitext markup. Download may take a while."
    ),
))

# -- HSE Thai Corpus --------------------------------------------------------
_register(CorpusInfo(
    name="hse",
    description=(
        "HSE Thai Corpus — ~50 million tokens downloaded from Thai websites, "
        "mostly news sites. Compiled by the Higher School of Economics."
    ),
    category="mixed",
    license="Unknown (research use)",
    source_url="https://web-corpora.net/ThaiCorpus/search/",
    download_urls=[
        # The HSE corpus does not have a single stable direct-download URL.
        # It may need to be obtained from web-corpora.net or academic sources.
        # This URL is a known mirror; update if it becomes unavailable.

        # Github mirror is dead (repo removed)
        # "https://github.com/Wikipedia2008/Thai-Corpus/archive/refs/heads/master.zip",

        "https://www.kaggle.com/datasets/rtatman/hse-thai-corpus"
    ],
    size_estimate="~200 MB (compressed)",
    notes=(
        "The HSE Thai Corpus download URL may change. If the automated "
        "download fails, visit https://web-corpora.net/ThaiCorpus/search/ "
        "for the latest access instructions. The GitHub mirror may contain "
        "a subset of the full corpus."
    ),
))


def list_corpora(verbose: bool = False) -> None:
    """Print a summary of all registered corpora.

    Args:
        verbose: If True, include full descriptions and notes.
    """
    print(f"{'Name':<14} {'Category':<10} {'Size':<30} {'License'}")
    print("-" * 75)
    for corpus in CORPUS_REGISTRY.values():
        print(
            f"{corpus.name:<14} {corpus.category:<10} "
            f"{corpus.size_estimate:<30} {corpus.license}"
        )
        if verbose:
            print(f"  {corpus.description}")
            if corpus.notes:
                print(f"  Note: {corpus.notes}")
            print(f"  Source: {corpus.source_url}")
            print()
