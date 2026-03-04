"""Download utilities for Thai NLP corpora.

Handles downloading, extracting, and verifying corpus data.
All raw data is stored in data/corpora/raw/{corpus_name}/ (gitignored).

Usage as module:
    from src.data.download import download_corpus
    download_corpus("prachathai")
    download_corpus("all")

Usage as CLI:
    python -m src.data.download --list
    python -m src.data.download prachathai
    python -m src.data.download prachathai wisesight wongnai
    python -m src.data.download --all
"""

import argparse
import shutil
import sys
import typing
import zipfile
import bz2
from pathlib import Path
from urllib.request import urlretrieve, Request, urlopen
from urllib.error import URLError, HTTPError

from src.data.registry import CORPUS_REGISTRY, RAW_DATA_DIR, list_corpora


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    """Print download progress."""
    if total_size > 0:
        downloaded = block_num * block_size
        percent = min(100, downloaded * 100 // total_size)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        print(
            f"\r  Progress: {percent:3d}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)",
            end="",
            flush=True,
        )
    else:
        downloaded = block_num * block_size
        mb_downloaded = downloaded / (1024 * 1024)
        print(f"\r  Downloaded: {mb_downloaded:.1f} MB", end="", flush=True)


def _download_file(url: str, dest: Path) -> Path:
    """Download a file from URL to dest path, with progress reporting.

    Args:
        url: URL to download from.
        dest: Local file path to save to.

    Returns:
        The dest path.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1].split("?")[0]
    print(f"  Downloading: {filename}")
    print(f"  From: {url}")

    try:
        urlretrieve(url, dest, reporthook=_progress_hook)
        print()  # newline after progress
    except (URLError, HTTPError) as e:
        print(f"\n  ERROR: Download failed: {e}")
        raise

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"  Saved: {dest} ({size_mb:.1f} MB)")

    # Detect Git LFS pointer files (small text files that start with
    # "version https://git-lfs.github.com/spec/v1").
    # This happens when downloading raw URLs from repos that use Git LFS.
    if dest.stat().st_size < 1024:
        try:
            head = dest.read_text(encoding="utf-8", errors="ignore")[:64]
            if "git-lfs.github.com" in head:
                dest.unlink()
                raise RuntimeError(
                    f"Downloaded file is a Git LFS pointer, not the actual data.\n"
                    f"  The source repo uses Git LFS for this file.\n"
                    f"  URL: {url}\n"
                    f"  Fix: Use a GitHub Release asset URL or Hugging Face instead."
                )
        except UnicodeDecodeError:
            pass  # binary file, not an LFS pointer

    return dest


def _extract_zip(zip_path: Path, extract_to: Path) -> None:
    """Extract a zip file."""
    print(f"  Extracting: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    print(f"  Extracted to: {extract_to}")


def _extract_bz2(bz2_path: Path, extract_to: Path) -> None:
    """Extract a bz2-compressed file."""
    output_name = bz2_path.stem  # remove .bz2 extension
    output_path = extract_to / output_name
    print(f"  Decompressing: {bz2_path.name}")
    with bz2.open(bz2_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            # Stream in chunks to handle large files
            while True:
                chunk = f_in.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                f_out.write(chunk)
    print(f"  Decompressed to: {output_path}")


# ---------------------------------------------------------------------------
# Per-corpus download handlers
# ---------------------------------------------------------------------------

def _download_prachathai(dest_dir: Path, force: bool = False) -> None:
    """Download and extract Prachathai 67K corpus."""
    corpus = CORPUS_REGISTRY["prachathai"]
    zip_path = dest_dir / "data.zip"
    _download_file(corpus.download_urls[0], zip_path)
    _extract_zip(zip_path, dest_dir)
    zip_path.unlink()  # clean up zip after extraction


def _download_wisesight(dest_dir: Path, force: bool = False) -> None:
    """Download Wisesight sentiment corpus (4 text files)."""
    corpus = CORPUS_REGISTRY["wisesight"]
    for url in corpus.download_urls:
        filename = url.split("/")[-1]
        file_path = dest_dir / filename
        _download_file(url, file_path)


def _download_wongnai(dest_dir: Path, force: bool = False) -> None:
    """Download and extract Wongnai review corpus."""
    corpus = CORPUS_REGISTRY["wongnai"]
    zip_path = dest_dir / "review_dataset.zip"
    _download_file(corpus.download_urls[0], zip_path)
    _extract_zip(zip_path, dest_dir)
    zip_path.unlink()


def _download_thwiki(dest_dir: Path, force: bool = False) -> None:
    """Download Thai Wikipedia dump (large file, ~500 MB compressed)."""
    corpus = CORPUS_REGISTRY["thwiki"]
    bz2_path = dest_dir / "thwiki-latest-pages-articles.xml.bz2"
    _download_file(corpus.download_urls[0], bz2_path)
    print(
        "  Note: The downloaded file is a compressed XML dump (~500 MB).\n"
        "  Decompression is skipped by default (output would be ~1.5 GB).\n"
        "  To decompress, run:\n"
        f"    bunzip2 {bz2_path}\n"
        "  Or use bz2 module in Python to stream-process the compressed file."
    )


def _download_hse(dest_dir: Path, force: bool = False) -> None:
    """Download HSE Thai Corpus."""
    corpus = CORPUS_REGISTRY["hse"]
    zip_path = dest_dir / "hse-thai-corpus.zip"
    try:
        _download_file(corpus.download_urls[0], zip_path)
        _extract_zip(zip_path, dest_dir)
        zip_path.unlink()
    except (URLError, HTTPError):
        print(
            "  WARNING: Automated download failed for HSE Thai Corpus.\n"
            "  This corpus may require manual download.\n"
            f"  Visit: {corpus.source_url}\n"
            "  Or check: https://github.com/Wikipedia2008/Thai-Corpus\n"
            f"  Place downloaded files in: {dest_dir}"
        )


# Map corpus names to their download handlers
_DOWNLOAD_HANDLERS: dict[str, typing.Callable] = {
    "prachathai": _download_prachathai,
    "wisesight": _download_wisesight,
    "wongnai": _download_wongnai,
    "thwiki": _download_thwiki,
    "hse": _download_hse,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_corpus(
    name: str,
    force: bool = False,
) -> None:
    """Download a corpus (or all corpora) by name.

    Args:
        name: Corpus name (e.g. 'prachathai') or 'all' for everything.
        force: If True, re-download even if the data directory already exists.
    """
    if name == "all":
        for corpus_name in CORPUS_REGISTRY:
            download_corpus(corpus_name, force=force)
        return

    if name not in CORPUS_REGISTRY:
        available = ", ".join(CORPUS_REGISTRY.keys())
        raise ValueError(
            f"Unknown corpus: '{name}'. Available: {available}"
        )

    corpus = CORPUS_REGISTRY[name]
    dest_dir = corpus.raw_dir()

    # Check if already downloaded
    if dest_dir.exists() and any(dest_dir.iterdir()) and not force:
        print(f"[{name}] Already downloaded at {dest_dir}")
        print(f"  Use --force to re-download.")
        return

    # Clean and create destination
    if dest_dir.exists() and force:
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Downloading: {corpus.name}")
    print(f"Description: {corpus.description}")
    print(f"License:     {corpus.license}")
    print(f"Dest:        {dest_dir}")
    print(f"{'='*60}")

    # Run the corpus-specific download handler
    handler = _DOWNLOAD_HANDLERS.get(name)
    if handler is None:
        raise NotImplementedError(
            f"No download handler for corpus '{name}'. "
            "Please implement one in src/data/download.py"
        )

    handler(dest_dir, force=force)

    # Verify something was downloaded
    files = list(dest_dir.rglob("*"))
    file_count = sum(1 for f in files if f.is_file())
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    total_mb = total_size / (1024 * 1024)

    print(f"\n  Done! {file_count} file(s), {total_mb:.1f} MB total")


def corpus_status() -> dict[str, bool]:
    """Check which corpora are already downloaded.

    Returns:
        Dict mapping corpus name to True if downloaded, False otherwise.
    """
    status = {}
    for name, corpus in CORPUS_REGISTRY.items():
        raw_dir = corpus.raw_dir()
        status[name] = raw_dir.exists() and any(raw_dir.iterdir())
    return status


def print_status() -> None:
    """Print download status of all corpora."""
    status = corpus_status()
    print(f"\n{'Name':<14} {'Status':<14} {'Path'}")
    print("-" * 65)
    for name, downloaded in status.items():
        corpus = CORPUS_REGISTRY[name]
        icon = "downloaded" if downloaded else "not downloaded"
        print(f"{name:<14} {icon:<14} {corpus.raw_dir()}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for downloading corpora."""
    parser = argparse.ArgumentParser(
        description="Download Thai NLP corpora for thaime-nlp research.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.data.download --list\n"
            "  python -m src.data.download --status\n"
            "  python -m src.data.download prachathai\n"
            "  python -m src.data.download prachathai wisesight wongnai\n"
            "  python -m src.data.download --all\n"
            "  python -m src.data.download --all --force\n"
        ),
    )
    parser.add_argument(
        "corpora",
        nargs="*",
        help="Corpus name(s) to download (e.g. 'prachathai wisesight').",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available corpora.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available corpora with metadata.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show download status of all corpora.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if data already exists.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed corpus information.",
    )

    args = parser.parse_args()

    if args.list:
        list_corpora(verbose=args.verbose)
        return

    if args.status:
        print_status()
        return

    if args.all:
        download_corpus("all", force=args.force)
        print("\n" + "=" * 60)
        print("All downloads complete!")
        print_status()
        return

    if not args.corpora:
        parser.print_help()
        sys.exit(1)

    for name in args.corpora:
        download_corpus(name, force=args.force)

    if len(args.corpora) > 1:
        print_status()


if __name__ == "__main__":
    main()
