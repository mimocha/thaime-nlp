"""CLI entry point for all THAIME pipelines.

Usage:
    python -m pipelines --help
    python -m pipelines trie run
    python -m pipelines ngram run
    python -m pipelines benchmark word-conversion run
"""

from __future__ import annotations

import click


@click.group()
@click.option("--no-cache", is_flag=True, default=False, help="Ignore cached files, force full rebuild")
@click.option("--workers", default=None, type=int, help="Override worker count for all sub-pipelines")
@click.pass_context
def cli(ctx, no_cache: bool, workers: int | None) -> None:
    """THAIME data generation pipelines."""
    ctx.ensure_object(dict)
    ctx.obj["no_cache"] = no_cache
    ctx.obj["workers"] = workers


# ---------------------------------------------------------------------------
# Register sub-pipeline groups
# ---------------------------------------------------------------------------


def _register_subcommands() -> None:
    """Lazily import and register pipeline subcommands."""
    from pipelines.trie.generate import cli as trie_cli
    from pipelines.ngram.generate import cli as ngram_cli
    from pipelines.benchmarks.word_conversion.generate import cli as benchmark_wc_cli
    from pipelines.llm_filter.cli import cli as llm_filter_cli

    cli.add_command(trie_cli, "trie")
    cli.add_command(ngram_cli, "ngram")
    cli.add_command(llm_filter_cli, "llm-filter")

    # Nested: benchmark -> word-conversion
    @cli.group()
    def benchmark():
        """Benchmark generation pipelines."""

    benchmark.add_command(benchmark_wc_cli, "word-conversion")


_register_subcommands()


if __name__ == "__main__":
    cli()
