# thaime-nlp

NLP research repository for the [THAIME](https://github.com/mimocha/thaime) project — a Latin-to-Thai input method engine.

This repo contains research experiments, benchmark datasets, and data pipelines that produce the dictionary data and language model parameters used by the main THAIME engine. It is designed for structured, reproducible research conducted by both human collaborators and AI agents.

## Related Repositories

- **[thaime](https://github.com/mimocha/thaime)** — Core engine (Rust) and framework frontends. The production codebase.

## How This Repo Works

Each research topic follows a four-stage workflow (background → plan → experiment → summary) on its own git branch. Completed research summaries are merged to `main` and indexed in [`research/index.md`](research/index.md). See [`docs/research-workflow.md`](docs/research-workflow.md) for the full process.

In addition to research, this repo contains production data pipelines in `pipelines/` that generate the dictionary data and language model parameters consumed by the main THAIME engine. See [`docs/git-workflow.md`](docs/git-workflow.md) for the pipeline development workflow.

## Research Topics

See [`research/index.md`](research/index.md) for all completed and in-progress research.

## Getting Started

### For contributors

1. Clone the repo and read the docs in `docs/`.
2. Create a research branch: `git checkout -b research/<topic-name>`, or a pipeline branch: `git checkout -b pipeline/<name>`
3. For research, follow the four-stage workflow in [`docs/research-workflow.md`](docs/research-workflow.md).
4. When done, create a clean `summary/<topic-name>` branch from `main` containing only the deliverable files (e.g. `summary.md`), then open a PR from `summary/` → `main`. For pipelines, open a PR directly from `pipeline/<name>` → `main`.

Research branches hold all experimental code and are kept for reference; only summary branches get merged via GitHub's standard UI. See [`docs/git-workflow.md`](docs/git-workflow.md) for full details.

### For AI agents

Start by reading [`CLAUDE.md`](CLAUDE.md) at the repo root.

## License

MIT
