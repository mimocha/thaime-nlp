"""LLM-based vocabulary filter for the trie generation pipeline.

Standalone script that uses Claude Sonnet via AWS Bedrock to identify
garbage tokens (tokenization artifacts, fragments, misspellings) in the
wordlist. Outputs an exclusion list of words to drop, for human review.

The workflow:
  1. Run 'generate' to produce a raw exclusion list via LLM review.
  2. Manually review the raw output, removing any legitimate words.
  3. Run 'approve' to copy the reviewed list to the data directory.
  4. The main pipeline reads the approved exclusion list during filtering.

Usage:
    # Generate raw exclusion list
    python -m pipelines.trie.llm_filter generate
    python -m pipelines.trie.llm_filter generate --batch-size 500
    python -m pipelines.trie.llm_filter generate --input path/to/wordlist.csv

    # Approve the reviewed exclusion list
    python -m pipelines.trie.llm_filter approve --version 1.0.0

Environment:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION (or AWS profile)
    must be configured for Bedrock access.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & defaults
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = _SCRIPT_DIR / "outputs" / "wordlist.csv"
DEFAULT_OUTPUT = _SCRIPT_DIR / "outputs" / "dropped_words_raw.txt"
EXCLUSIONS_DIR = (
    _SCRIPT_DIR.parent.parent / "data" / "dictionaries" / "word_exclusions"
)

DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"
DEFAULT_BATCH_SIZE = 1000
DEFAULT_REGION = "us-east-1"

# Default limit on number of words to process from the wordlist (for testing)
RAW_WORDLIST_LIMIT = 5000

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

# System prompt — static instructions, cached across batches.
FILTER_SYSTEM_PROMPT = """\
Review the following list of Thai words and identify garbage tokens that
should be excluded from the vocabulary of an Input Method Editor.

Flag for removal:
- Gibberish or random character sequences
- Word fragments and tokenization artifacts (e.g., ๆแล้ว, ทร์, ผลื)
- Obvious misspellings or misinputs
- Non-Thai text that isn't a commonly used loanword
- Repetition artifacts (e.g., ๆๆ)

Do NOT flag (these should be KEPT):
- Common phrases and compound words (e.g., แล้วก็, ไปแล้ว, ทำไม)
- Common colloquial/informal variants (e.g., คับ, มั้ย, จ้ะ, อะ)
- Thai particles and interjections
- Name entities (people, places, brands)
- Thai abbreviations and acronyms
- Loanwords (e.g., คอมพิวเตอร์, เซลฟี่)

Generally try to flag tokens which users are unlikely to type.
Return the words to remove inside a code fence, one per line.
Do not include any other text inside the code fence.
If all words look valid, return an empty code fence."""

# User message template — only the word list changes per batch.
FILTER_USER_PROMPT = """\
<words>
{words}
</words>"""

# Regex to extract content from a code fence in the response.
_CODE_FENCE_RE = re.compile(r"```\s*\n?(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_wordlist(path: Path, limit: int) -> list[str]:
    """Read Thai words from wordlist CSV (expects 'thai_word' column)."""
    words: list[str] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            words.append(row["thai_word"])
            if len(words) >= limit:
                break
    return words


def chunk_words(words: list[str], batch_size: int) -> list[list[str]]:
    """Split word list into batches of batch_size."""
    return [words[i : i + batch_size] for i in range(0, len(words), batch_size)]


@dataclass
class BatchResult:
    """Result from a single LLM batch call."""

    batch_idx: int
    batch_size: int
    raw_text: str = ""
    parsed_words: list[str] = field(default_factory=list)
    valid_dropped: list[str] = field(default_factory=list)
    invalid_words: list[str] = field(default_factory=list)
    cache_write: int = 0
    cache_read: int = 0
    error: str | None = None


def call_bedrock(
    client: object,
    model_id: str,
    batch_idx: int,
    words: list[str],
) -> BatchResult:
    """Call Bedrock with a batch of words. Thread-safe (no prints)."""
    result = BatchResult(batch_idx=batch_idx, batch_size=len(words))

    try:
        user_prompt = FILTER_USER_PROMPT.format(words="\n".join(words))

        response = client.invoke_model(  # type: ignore[union-attr]
            modelId=model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8192,
                    "temperature": 0.1,
                    "system": [
                        {
                            "type": "text",
                            "text": FILTER_SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": user_prompt}],
                }
            ),
            contentType="application/json",
        )

        body = json.loads(response["body"].read())  # type: ignore[index]
        result.raw_text = body["content"][0]["text"].strip()

        # Cache usage stats
        usage = body.get("usage", {})
        result.cache_write = usage.get("cache_creation_input_tokens", 0)
        result.cache_read = usage.get("cache_read_input_tokens", 0)

        if not result.raw_text:
            return result

        # Extract words from inside the code fence
        match = _CODE_FENCE_RE.search(result.raw_text)
        if match:
            inner = match.group(1).strip()
            result.parsed_words = (
                [line.strip() for line in inner.split("\n") if line.strip()]
                if inner
                else []
            )
        else:
            # Fallback: treat entire response as word list
            result.parsed_words = [
                line.strip()
                for line in result.raw_text.split("\n")
                if line.strip()
            ]

        # Validate against input batch
        batch_set = set(words)
        result.valid_dropped = [w for w in result.parsed_words if w in batch_set]
        result.invalid_words = [
            w for w in result.parsed_words if w not in batch_set
        ]

    except Exception as e:
        result.error = str(e)

    return result


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


DEFAULT_WORKERS = 4


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate raw exclusion list by running LLM filter on the wordlist."""
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 is required. Install with: uv pip install boto3")
        sys.exit(1)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Wordlist not found at {input_path}")
        print("  Run the trie pipeline first to generate wordlist.csv.")
        sys.exit(1)

    print(f"Reading wordlist from {input_path}")
    words = read_wordlist(input_path, limit=args.limit)
    print(f"  Total words: {len(words):,}")

    batches = chunk_words(words, args.batch_size)
    num_batches = len(batches)
    workers = min(args.workers, num_batches)
    print(f"  Batches: {num_batches} × {args.batch_size} words")
    print(f"  Workers: {workers}")
    print(f"  Model: {args.model}")
    print(f"  Region: {args.region}")

    # Set up Bedrock client (thread-safe for invoke_model)
    client = boto3.client("bedrock-runtime", region_name=args.region)

    # Log file for raw LLM responses (append mode — accumulates across runs)
    log_path = output_path.parent / "llm_filter.log"
    run_ts = time.strftime("%Y-%m-%d %H:%M:%S")

    # -----------------------------------------------------------------------
    # Submit all batches concurrently
    # -----------------------------------------------------------------------
    print(f"\n  Submitting {num_batches} batches...")
    t_start = time.monotonic()

    results: dict[int, BatchResult] = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(call_bedrock, client, args.model, i, batch): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            br = future.result()
            results[br.batch_idx] = br
            completed += 1

            # Progress line
            status = f"dropped {len(br.valid_dropped)}"
            if br.error:
                status = f"ERROR: {br.error}"
            cache_info = ""
            if br.cache_write or br.cache_read:
                cache_info = f" [cache: w={br.cache_write}, r={br.cache_read}]"
            if br.invalid_words:
                status += f" ({len(br.invalid_words)} invalid)"
            print(
                f"  [{completed}/{num_batches}] "
                f"Batch {br.batch_idx + 1}: {status}{cache_info}"
            )

    elapsed = time.monotonic() - t_start

    # -----------------------------------------------------------------------
    # Write log file in batch order
    # -----------------------------------------------------------------------
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"\n{'=' * 72}\n")
        log_file.write(f"RUN: {run_ts}\n")
        log_file.write(f"Model: {args.model} | Region: {args.region}\n")
        log_file.write(f"Input: {input_path} | Limit: {args.limit}\n")
        log_file.write(
            f"Words: {len(words):,} | Batches: {num_batches} × {args.batch_size}"
            f" | Workers: {workers}\n"
        )
        log_file.write(f"Elapsed: {elapsed:.1f}s\n")
        log_file.write(f"{'=' * 72}\n")

        for idx in range(num_batches):
            br = results[idx]
            word_start = idx * args.batch_size + 1
            word_end = idx * args.batch_size + br.batch_size
            log_file.write(
                f"\n--- Batch {idx + 1}/{num_batches} "
                f"(words {word_start}-{word_end}) ---\n"
            )
            if br.error:
                log_file.write(f"ERROR: {br.error}\n")
            else:
                log_file.write(br.raw_text)
                log_file.write("\n")
                if br.invalid_words:
                    log_file.write(f"WARNING: invalid words: {br.invalid_words}\n")
                log_file.write(
                    f"PARSED: {len(br.parsed_words)} raw, "
                    f"{len(br.valid_dropped)} valid, "
                    f"{len(br.invalid_words)} invalid\n"
                )

    print(f"  Log file: {log_path}")

    # -----------------------------------------------------------------------
    # Aggregate results in batch order
    # -----------------------------------------------------------------------
    all_dropped: list[str] = []
    failed_batches: list[int] = []

    for idx in range(num_batches):
        br = results[idx]
        if br.error:
            failed_batches.append(idx + 1)
        else:
            all_dropped.extend(br.valid_dropped)

    # Deduplicate and sort
    all_dropped = sorted(set(all_dropped))

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for word in all_dropped:
            f.write(word + "\n")

    print(f"\n{'=' * 60}")
    print("Results:")
    print(f"  Total words reviewed:  {len(words):>8,}")
    print(f"  Words flagged to drop: {len(all_dropped):>8,}")
    print(f"  Words kept:            {len(words) - len(all_dropped):>8,}")
    print(f"  Elapsed:               {elapsed:>7.1f}s")
    if failed_batches:
        print(f"  Failed batches:        {failed_batches}")
    print(f"  Output: {output_path}")
    print()
    print("Next steps:")
    print("  1. Review the output file, remove any legitimate words.")
    print("  2. Run: python -m pipelines.trie.llm_filter approve --version 1.0.0")


def cmd_approve(args: argparse.Namespace) -> None:
    """Copy the reviewed exclusion list to the data directory."""
    raw_path = Path(args.input)
    version = args.version
    dest = EXCLUSIONS_DIR / f"exclusions-v{version}.txt"

    if not raw_path.exists():
        print(f"ERROR: Exclusion list not found at {raw_path}")
        print("  Run 'generate' first, then review the output.")
        sys.exit(1)

    # Read and validate
    with open(raw_path, encoding="utf-8") as f:
        words = sorted({line.strip() for line in f if line.strip()})

    print(f"Approving exclusion list v{version}")
    print(f"  Source: {raw_path}")
    print(f"  Words:  {len(words):,}")
    print(f"  Dest:   {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        for word in words:
            f.write(word + "\n")

    print(f"  Done. Exclusion list saved.")
    print()
    print("To use in the pipeline, run:")
    print(f"  python -m pipelines.trie.generate --exclusion-list {dest}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-based vocabulary filter for the trie pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- generate --
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate raw exclusion list using LLM",
    )
    gen_parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help=f"Path to wordlist CSV (default: {DEFAULT_INPUT})",
    )
    gen_parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Path for raw output (default: {DEFAULT_OUTPUT})",
    )
    gen_parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Words per LLM batch (default: {DEFAULT_BATCH_SIZE})",
    )
    gen_parser.add_argument(
        "--limit",
        type=int,
        default=RAW_WORDLIST_LIMIT,
        help=f"Max words to process from the wordlist (default: {RAW_WORDLIST_LIMIT})",
    )
    gen_parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Concurrent API calls (default: {DEFAULT_WORKERS})",
    )
    gen_parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_ID,
        help=f"Bedrock model ID (default: {DEFAULT_MODEL_ID})",
    )
    gen_parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: {DEFAULT_REGION})",
    )

    # -- approve --
    app_parser = subparsers.add_parser(
        "approve",
        help="Approve reviewed exclusion list and copy to data directory",
    )
    app_parser.add_argument(
        "--input",
        default=str(DEFAULT_OUTPUT),
        help=f"Path to reviewed raw file (default: {DEFAULT_OUTPUT})",
    )
    app_parser.add_argument(
        "--version",
        required=True,
        help="Version string (e.g., 1.0.0)",
    )

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "approve":
        cmd_approve(args)


if __name__ == "__main__":
    main()
