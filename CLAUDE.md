# CLAUDE.md — Agent Instructions for thaime-nlp

## What Is This Repo?

`thaime-nlp` is the NLP research repository for the [THAIME](https://github.com/mimocha/thaime) project — a Latin-to-Thai input method engine. This repo contains research experiments, benchmarks, and data pipelines that produce artifacts consumed by the main `thaime` engine.

This repo is designed for **agentic research** — Claude agents (and human collaborators) conduct structured experiments following standardized workflows. The maintainer oversees research directions and reviews final results.

## Quick Orientation

Read these documents in order before starting any work:

1. **This file** — You are here. High-level orientation.
2. **[docs/git-workflow.md](docs/git-workflow.md)** — How branching, commits, and pull requests work in this repo.
3. **[docs/research-workflow.md](docs/research-workflow.md)** — The four-stage research process (Background → Plan → Experiment → Summary).
4. **[docs/research-template.md](docs/research-template.md)** — Templates for each research artifact.
5. **[docs/benchmarks.md](docs/benchmarks.md)** — How to use and extend the standardized test datasets.

## Repo Structure

```
thaime-nlp/
├── CLAUDE.md                   # This file (agent entry point)
├── README.md                   # Human-readable project overview
├── LICENSE                     # MIT
├── .gitignore
├── pyproject.toml              # Python project & dependencies
│
├── .devcontainer/              # Dev container configuration
│   └── devcontainer.json
│
├── docs/                       # Repo-level documentation
│   ├── git-workflow.md         # Branching and PR conventions
│   ├── research-workflow.md    # The four-stage research process
│   ├── research-template.md   # Templates for research artifacts
│   └── benchmarks.md          # Benchmark dataset documentation
│
├── research/                   # Completed research (merged to main)
│   ├── index.md               # Master index of all completed research
│   └── <topic-name>/          # One directory per completed topic
│       └── summary.md         # Final summary (the key deliverable)
│
├── benchmarks/                 # Standardized test datasets
│   ├── word-conversion/       # Latin input → Thai output pairs
│   ├── segmentation/          # Multi-word segmentation test cases
│   └── ranking/               # Candidate ranking evaluation sets
│
├── data/                       # Shared datasets and dictionaries
│   ├── corpora/               # Processed corpus data
│   └── dictionaries/          # Word lists, frequency tables
│
├── pipelines/                  # Production data generation pipelines
│   └── <pipeline-name>/       # One directory per pipeline
│       ├── README.md          # Pipeline documentation
│       └── *.py               # Pipeline code
│
├── src/                        # Shared utility code
│   └── utils/                 # Common helpers (evaluation, data loading, etc.)
│
└── experiments/                # Active experiment workspaces (on research branches)
    └── .gitkeep
```

## Key Rules

1. **Never modify benchmarks without explicit maintainer approval.** Benchmark datasets in `benchmarks/` are the ground truth. If you believe a benchmark needs changes, document your reasoning in the research summary and propose additions — do not modify existing entries.

2. **Follow the research workflow.** Every experiment follows the four stages defined in `docs/research-workflow.md`. Do not skip stages.

3. **Use Python for all research code.** This repo is Python-only. Research code does not need to be production-quality, but it must be runnable and reproducible (document dependencies in `pyproject.toml` or use inline `uv pip install` commands).

4. **Keep research branches self-contained.** Each `research/<topic>` branch should contain everything needed to reproduce its results. Do not depend on state from other research branches.

5. **Only summaries merge to main.** When a research topic is complete, only the summary document (and any new shared utilities or benchmark additions) merge into `main` via pull request. Experimental notebooks and intermediate artifacts stay on the research branch for reference.

## Pipeline Work

- Pipelines live in `pipelines/` and follow the `pipeline/<name>` branching convention (see `docs/git-workflow.md`).
- Pipeline code should be production-quality: proper error handling, logging, docstrings, and a README documenting inputs, outputs, configuration, and how to run.
- Pipelines import shared modules from `src/` — do not duplicate code from `src/` into pipeline directories.
- Pipeline outputs (generated data files) are `.gitignore`'d. The pipeline must be runnable to regenerate outputs on demand. Stable outputs are published via GitHub Releases.
- Pipeline code uses Python, same as research code. Dependencies go in `pyproject.toml`.

## Tech Stack

- **Language:** Python 3.10+
- **Key libraries:** PyThaiNLP, TLTK, pandas, numpy, matplotlib, jupyter (see `pyproject.toml`)
- **Testing:** pytest for shared utilities; benchmark evaluation scripts in `src/utils/`
- **Environment:** A devcontainer is provided in `.devcontainer/` with all dependencies pre-installed. For local development, use `uv sync` to create a venv and install dependencies.

## Context From the Main Project

The main `thaime` repo contains three key reference documents. If you need architectural context, ask the maintainer to provide them or refer to these summaries:

- **Conversion algorithm** — THAIME uses a two-stage pipeline: (1) fuzzy prefix search on a multi-romanization trie to build a word lattice, (2) Viterbi algorithm with n-gram language model scoring to find the best path. See `thaime-conversion-algorithm.md` in the main project.
- **Architecture** — The engine is a Rust shared library (libthaime) with C ABI, consumed by IBus/Fcitx5 frontends. This repo produces the dictionary data and language model parameters that the engine loads at runtime.
- **Roadmap** — The 2026 roadmap targets a working IBus IME by Q2, with Fcitx5 support by Q3. Research in this repo directly feeds into engine development.
