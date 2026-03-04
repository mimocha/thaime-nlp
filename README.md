# thaime-nlp

NLP research repository for the [THAIME](https://github.com/mimocha/thaime) project — a Latin-to-Thai input method engine.

This repo contains research experiments, benchmark datasets, and data pipelines that produce the dictionary data and language model parameters used by the main THAIME engine. It is designed for structured, reproducible research conducted by both human collaborators and AI agents.

## Related Repositories

- **[thaime](https://github.com/mimocha/thaime)** — Core engine (Rust) and framework frontends. The production codebase.
- **[thaime-candidate](https://github.com/mimocha/thaime-candidate)** — Earlier NLP research and prototyping (predecessor to this repo).

## How This Repo Works

Each research topic follows a four-stage workflow (background → plan → experiment → summary) on its own git branch. Completed research summaries are merged to `main` and indexed in [`research/index.md`](research/index.md). See [`docs/research-workflow.md`](docs/research-workflow.md) for the full process.

## Research Topics

See [`research/index.md`](research/index.md) for all completed and in-progress research.

## Getting Started

### For contributors

1. Clone the repo and read the docs in `docs/`.
2. Create a research branch: `git checkout -b research/<topic-name>`
3. Follow the workflow in [`docs/research-workflow.md`](docs/research-workflow.md).

### For AI agents

Start by reading [`CLAUDE.md`](CLAUDE.md) at the repo root.

## License

MIT
