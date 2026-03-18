"""CLI entry point for all THAIME pipelines.

Usage:
    python -m pipelines --help
    python -m pipelines trie run
    python -m pipelines ngram run
    python -m pipelines smoke-test
    python -m pipelines benchmark word-conversion run
"""

from __future__ import annotations

from pathlib import Path

import click

from pipelines.config import OUTPUT_DIR
from pipelines.console import console


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
# Smoke test command
# ---------------------------------------------------------------------------


@cli.command("smoke-test")
@click.option(
    "--data-dir",
    type=click.Path(exists=True, path_type=Path),
    default=OUTPUT_DIR,
    help="Path to pipeline outputs directory.",
)
@click.option(
    "--test-cases",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to test_cases.yaml (defaults to bundled file).",
)
@click.option(
    "--beam-width",
    type=int,
    default=10,
    help="Beam width for Viterbi search.",
)
def smoke_test(data_dir: Path, test_cases: Path | None, beam_width: int) -> None:
    """Run smoke tests against pipeline artifacts."""
    from src.utils.smoke_test import run_smoke_tests

    console.print()
    console.print("=" * 60)
    console.print("Smoke Test")
    console.print("=" * 60)
    console.print(f"  Data directory: {data_dir}")
    console.print(f"  Beam width: {beam_width}")
    if test_cases:
        console.print(f"  Test cases: {test_cases}")
    console.print()

    results = run_smoke_tests(
        data_dir=data_dir,
        test_cases_path=test_cases,
        beam_width=beam_width,
    )

    # Print results
    n_pass = sum(1 for r in results if r.status == "pass")
    n_warn = sum(1 for r in results if r.status == "warn")
    n_fail = sum(1 for r in results if r.status == "fail")

    for r in results:
        if r.status == "pass":
            icon = "[green]PASS[/green]"
        elif r.status == "warn":
            icon = f"[yellow]WARN (rank {r.rank})[/yellow]"
        else:
            icon = "[red]FAIL[/red]"

        console.print(f"  {icon}  {r.input!r} → {r.expected}")
        if r.status != "pass" and r.top_result:
            console.print(f"         got: {r.top_result} (score: {r.top_score:.4f})")
        if r.note:
            console.print(f"         note: {r.note}")

    console.print()
    console.print(f"  Results: {n_pass} pass, {n_warn} warn, {n_fail} fail "
                  f"({len(results)} total)")

    if n_fail > 0:
        console.print("  [red]Smoke test FAILED.[/red]")
        raise SystemExit(1)
    elif n_warn > 0:
        console.print("  [yellow]Smoke test passed with warnings.[/yellow]")
    else:
        console.print("  [green]All smoke tests passed.[/green]")


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
