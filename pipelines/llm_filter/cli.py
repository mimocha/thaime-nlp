"""Click CLI for the LLM vocabulary filter pipeline.

Usage:
    python -m pipelines llm-filter generate
    python -m pipelines llm-filter generate --batch-size 500
    python -m pipelines llm-filter approve --version 1.0.0
"""

from __future__ import annotations

from pathlib import Path

import click

from pipelines.config import LlmFilterConfig

_cfg = LlmFilterConfig()


@click.group()
def cli():
    """LLM-based vocabulary filter for the trie pipeline."""


@cli.command()
@click.option("--input", "input_path", default=None, type=click.Path(), help="Path to wordlist CSV")
@click.option("--output", "output_path", default=None, type=click.Path(), help="Path for raw output")
@click.option("--batch-size", default=_cfg.batch_size, type=int, help=f"Words per LLM batch (default: {_cfg.batch_size})")
@click.option("--limit", default=_cfg.wordlist_limit, type=int, help=f"Max words to process (default: {_cfg.wordlist_limit})")
@click.option("--workers", default=_cfg.num_workers, type=int, help=f"Concurrent API calls (default: {_cfg.num_workers})")
@click.option("--model", default=_cfg.model_id, help=f"Bedrock model ID (default: {_cfg.model_id})")
@click.option("--region", default=_cfg.region, help=f"AWS region (default: {_cfg.region})")
def generate(input_path, output_path, batch_size, limit, workers, model, region):
    """Generate raw exclusion list using LLM review."""
    from pipelines.llm_filter.generate import cmd_generate

    inp = Path(input_path) if input_path else _cfg.wordlist_path
    out = Path(output_path) if output_path else _cfg.output_dir / "dropped_words_raw.txt"

    cmd_generate(
        input_path=inp,
        output_path=out,
        batch_size=batch_size,
        limit=limit,
        workers=workers,
        model=model,
        region=region,
    )


@cli.command()
@click.option("--input", "input_path", default=None, type=click.Path(), help="Path to reviewed raw file")
@click.option("--version", required=True, help="Version string (e.g., 1.0.0)")
def approve(input_path, version):
    """Approve reviewed exclusion list and copy to data directory."""
    from pipelines.llm_filter.generate import cmd_approve

    inp = Path(input_path) if input_path else _cfg.output_dir / "dropped_words_raw.txt"

    cmd_approve(
        input_path=inp,
        version=version,
        exclusions_dir=_cfg.exclusions_dir,
    )
