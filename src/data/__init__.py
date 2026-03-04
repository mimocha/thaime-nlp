"""Data management utilities for thaime-nlp.

This package provides corpus registry, download, and loading utilities.

Usage:
    from src.data import CORPUS_REGISTRY, download_corpus, list_corpora

    # List available corpora
    list_corpora()

    # Download a specific corpus
    download_corpus("prachathai")

    # Download all corpora
    download_corpus("all")
"""


def __getattr__(name: str):
    """Lazy imports to avoid circular import warnings when running as __main__."""
    if name in ("CORPUS_REGISTRY", "CorpusInfo", "list_corpora"):
        from src.data.registry import CORPUS_REGISTRY, CorpusInfo, list_corpora

        globals()["CORPUS_REGISTRY"] = CORPUS_REGISTRY
        globals()["CorpusInfo"] = CorpusInfo
        globals()["list_corpora"] = list_corpora
        return globals()[name]
    if name == "download_corpus":
        from src.data.download import download_corpus

        globals()["download_corpus"] = download_corpus
        return download_corpus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CORPUS_REGISTRY",
    "CorpusInfo",
    "list_corpora",
    "download_corpus",
]
