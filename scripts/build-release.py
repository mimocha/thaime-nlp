#!/usr/bin/env python3
"""Build-release script for THAIME NLP pipeline artifacts.

Runs pipelines, collects artifacts, compresses them, generates checksums
and a manifest, and prints a ready-to-use ``gh release create`` command.

Usage:
    python scripts/build-release.py v0.1.0
    python scripts/build-release.py v0.1.0 --skip-pipelines
    python scripts/build-release.py v0.1.0 --skip-smoke-test
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINES_OUTPUT = REPO_ROOT / "pipelines" / "outputs"
RELEASE_DIR = PIPELINES_OUTPUT / "release"

# Artifacts to collect (relative to PIPELINES_OUTPUT)
ARTIFACT_PATHS: list[str] = [
    "trie/trie_dataset.json",
    "ngram/thaime_ngram_v1_mc15.bin",
    "ngram/ngrams_1_merged_raw.tsv",
    "ngram/ngrams_2_merged_raw.tsv",
    "ngram/ngrams_3_merged_raw.tsv",
]

# Input data directories for version resolution
INPUT_VERSIONS: dict[str, tuple[str, str]] = {
    # key: (directory relative to REPO_ROOT, glob pattern)
    "overrides": ("data/dictionaries/word_overrides", "overrides-v*.yaml"),
    "exclusions": ("data/dictionaries/word_exclusions", "exclusions-v*.txt"),
    "component_romanization": (
        "data/dictionaries/component-romanization",
        "dictionary-v*.yaml",
    ),
    "benchmark_word_conversion": ("benchmarks/word-conversion", "v*.csv"),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
SEMVER_RE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def resolve_latest_version(directory: Path, pattern: str) -> str:
    """Return the semver string (e.g. 'v0.5.0') of the latest matching file."""
    matches: list[tuple[tuple[int, int, int], str]] = []
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        m = SEMVER_RE.search(path.name)
        if m:
            ver = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            matches.append((ver, m.group(0)))
    if not matches:
        return "unknown"
    matches.sort(key=lambda x: x[0])
    return matches[-1][1]


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def gzip_file(src: Path, dst: Path) -> None:
    """Gzip-compress src to dst."""
    with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


def git_commit_hash() -> str:
    """Return the current HEAD commit hash (short)."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def git_commit_hash_full() -> str:
    """Return the current HEAD commit hash (full)."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def git_is_clean() -> bool:
    """Check if working tree is clean."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip() == ""


def git_current_branch() -> str:
    """Return the current branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def run_cmd(args: list[str], description: str) -> None:
    """Run a command, exit on failure."""
    print(f"\n>>> {description}")
    print(f"    $ {' '.join(args)}")
    result = subprocess.run(args, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"\nERROR: {description} failed (exit code {result.returncode})")
        sys.exit(1)


def fetch_previous_checksums() -> dict[str, str]:
    """Fetch checksums from the latest GitHub release body.

    Parses lines matching: ``sha256:<filename>:<hash>``

    Returns:
        Mapping of filename to sha256 hex digest.
    """
    result = subprocess.run(
        ["gh", "release", "view", "--json", "body", "-q", ".body"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return {}

    checksums: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("sha256:"):
            parts = line.split(":")
            if len(parts) == 3:
                checksums[parts[1]] = parts[2]
    return checksums


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and stage a THAIME NLP release.",
    )
    parser.add_argument(
        "version",
        help="Release version tag (e.g. v0.1.0)",
    )
    parser.add_argument(
        "--skip-pipelines",
        action="store_true",
        help="Skip pipeline rebuild (use existing outputs)",
    )
    parser.add_argument(
        "--skip-smoke-test",
        action="store_true",
        help="Skip smoke test",
    )
    args = parser.parse_args()

    version: str = args.version

    # -----------------------------------------------------------------------
    # 1. Validate
    # -----------------------------------------------------------------------
    if not VERSION_RE.match(version):
        print(f"ERROR: Version must match vMAJOR.MINOR.PATCH, got: {version}")
        sys.exit(1)

    branch = git_current_branch()
    if branch != "main":
        print(f"WARNING: Not on 'main' branch (current: {branch})")

    if not git_is_clean():
        print("WARNING: Working tree has uncommitted changes")

    # -----------------------------------------------------------------------
    # 2. Run pipelines
    # -----------------------------------------------------------------------
    if not args.skip_pipelines:
        # Strip leading 'v' for the trie metadata version string
        run_cmd(
            [sys.executable, "-m", "pipelines", "trie", "run",
             "--release-version", version],
            "Trie pipeline",
        )
        run_cmd(
            [sys.executable, "-m", "pipelines", "ngram", "run"],
            "N-gram pipeline",
        )
    else:
        print("\n>>> Skipping pipeline rebuild (--skip-pipelines)")

    # -----------------------------------------------------------------------
    # 3. Smoke test
    # -----------------------------------------------------------------------
    if not args.skip_smoke_test:
        run_cmd(
            [sys.executable, "-m", "pipelines", "smoke-test"],
            "Smoke test",
        )
    else:
        print("\n>>> Skipping smoke test (--skip-smoke-test)")

    # -----------------------------------------------------------------------
    # 4. Collect & compress artifacts
    # -----------------------------------------------------------------------
    print("\n>>> Collecting artifacts")
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, dict] = {}
    missing = []

    for rel_path in ARTIFACT_PATHS:
        src = PIPELINES_OUTPUT / rel_path
        if not src.exists():
            missing.append(rel_path)
            continue

        gz_name = src.name + ".gz"
        gz_path = RELEASE_DIR / gz_name

        uncompressed_size = src.stat().st_size
        gzip_file(src, gz_path)
        compressed_size = gz_path.stat().st_size
        checksum = sha256_file(gz_path)

        artifacts[gz_name] = {
            "sha256": checksum,
            "size_bytes": compressed_size,
            "uncompressed_size_bytes": uncompressed_size,
        }
        print(f"    {gz_name}: {compressed_size / 1024 / 1024:.1f} MB "
              f"(from {uncompressed_size / 1024 / 1024:.1f} MB)")

    if missing:
        print(f"\nERROR: Missing artifacts: {', '.join(missing)}")
        print("Run without --skip-pipelines to generate them.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 5. SHA-256 checksums file
    # -----------------------------------------------------------------------
    checksums_path = RELEASE_DIR / "sha256sums.txt"
    with open(checksums_path, "w") as f:
        for name, info in sorted(artifacts.items()):
            f.write(f"{info['sha256']}  {name}\n")
    print(f"\n>>> Checksums written to {checksums_path}")

    # -----------------------------------------------------------------------
    # 6. Compare against previous release
    # -----------------------------------------------------------------------
    print("\n>>> Comparing against previous release")
    prev_checksums = fetch_previous_checksums()
    hash_diff: list[str] = []

    if not prev_checksums:
        print("    No previous release found (or gh CLI not configured)")
    else:
        for name, info in sorted(artifacts.items()):
            prev = prev_checksums.get(name)
            if prev is None:
                hash_diff.append(f"    NEW       {name}")
            elif prev == info["sha256"]:
                hash_diff.append(f"    UNCHANGED {name}")
            else:
                hash_diff.append(f"    CHANGED   {name}")

        for line in hash_diff:
            print(line)

        # Warn if everything is unchanged
        unchanged = sum(1 for d in hash_diff if "UNCHANGED" in d)
        if unchanged == len(artifacts):
            print("\n    WARNING: All artifacts unchanged from previous release!")

    # -----------------------------------------------------------------------
    # 7. Resolve input data versions
    # -----------------------------------------------------------------------
    print("\n>>> Resolving input data versions")
    input_versions: dict[str, str] = {}
    for key, (rel_dir, pattern) in INPUT_VERSIONS.items():
        directory = REPO_ROOT / rel_dir
        ver = resolve_latest_version(directory, pattern)
        input_versions[key] = ver
        print(f"    {key}: {ver}")

    # -----------------------------------------------------------------------
    # 8. Generate manifest
    # -----------------------------------------------------------------------
    manifest = {
        "release": version,
        "commit": git_commit_hash_full(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs": input_versions,
        "artifacts": artifacts,
    }

    manifest_path = RELEASE_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"\n>>> Manifest written to {manifest_path}")

    # Copy manifest to release dir (not compressed — included as-is)
    # Already there since we wrote it directly to RELEASE_DIR

    # -----------------------------------------------------------------------
    # 9. Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Release Build Summary")
    print("=" * 60)
    print(f"  Version:  {version}")
    print(f"  Commit:   {manifest['commit'][:12]}")
    print(f"  Staged:   {RELEASE_DIR}")
    print()
    print(f"  {'Artifact':<40} {'Size':>10}")
    print(f"  {'-' * 40} {'-' * 10}")
    for name, info in sorted(artifacts.items()):
        size_mb = info["size_bytes"] / 1024 / 1024
        print(f"  {name:<40} {size_mb:>9.1f}M")

    if hash_diff:
        print()
        print("  Hash comparison:")
        for line in hash_diff:
            print(f"  {line.strip()}")

    warnings: list[str] = []
    if branch != "main":
        warnings.append(f"Not on main branch (on {branch})")
    if not git_is_clean():
        warnings.append("Working tree has uncommitted changes")
    if args.skip_pipelines:
        warnings.append("Pipelines were skipped (--skip-pipelines)")
    if args.skip_smoke_test:
        warnings.append("Smoke test was skipped (--skip-smoke-test)")

    if warnings:
        print()
        print("  Warnings:")
        for w in warnings:
            print(f"    - {w}")

    # -----------------------------------------------------------------------
    # 10. Print gh release create command
    # -----------------------------------------------------------------------
    # Build release body
    body_lines = [
        f"## THAIME NLP {version}",
        "",
        "### Artifacts",
        "",
        f"| File | Size |",
        f"|---|---|",
    ]
    for name, info in sorted(artifacts.items()):
        size_mb = info["size_bytes"] / 1024 / 1024
        body_lines.append(f"| `{name}` | {size_mb:.1f} MB |")

    body_lines += [
        "",
        "### Input Data Versions",
        "",
    ]
    for key, ver in sorted(input_versions.items()):
        body_lines.append(f"- {key}: `{ver}`")

    body_lines += [
        "",
        "### Smoke Test",
        "",
        "Passed" if not args.skip_smoke_test else "Skipped",
        "",
        "### SHA-256 Checksums",
        "",
        "```",
    ]
    for name, info in sorted(artifacts.items()):
        body_lines.append(f"sha256:{name}:{info['sha256']}")
    body_lines += [
        "```",
    ]

    body = "\n".join(body_lines)

    # Build the asset flags
    asset_flags = " \\\n    ".join(
        f'"{RELEASE_DIR / name}"'
        for name in sorted(artifacts.keys())
    )

    print()
    print("=" * 60)
    print("To publish this release, run:")
    print("=" * 60)
    print()
    print(f"gh release create {version} \\")
    print(f'    --title "THAIME NLP {version}" \\')
    print(f"    --notes \"$(cat <<'RELEASE_EOF'")
    print(body)
    print("RELEASE_EOF")
    print(f')\" \\')
    print(f"    {asset_flags} \\")
    print(f'    "{RELEASE_DIR / "manifest.json"}"')
    print()


if __name__ == "__main__":
    main()
