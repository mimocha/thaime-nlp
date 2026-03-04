# Git Workflow — thaime-nlp

## Branching Model

This repo uses a simplified two-tier branching model designed for research workflows:

```
main ─────────────────────────────────────────────────
  │                         ↑ (PR: summary only)
  ├── research/roman-coverage ──────────┘
  │                         ↑ (PR: summary only)
  ├── research/trie-comparison ─────────┘
  │                         ↑ (PR: summary only)
  └── research/ngram-smoothing ─────────┘
```

### `main` branch

The stable branch. Contains:
- All repo infrastructure (docs, benchmarks, shared utilities)
- Completed research summaries in `research/<topic>/summary.md`
- The research index at `research/index.md`

**Direct commits to `main` are allowed only for:**
- Documentation updates (docs/, README.md, CLAUDE.md)
- Benchmark additions (with maintainer approval)
- Shared utility code in `src/`
- Research index updates

### `research/<topic-name>` branches

Each research topic gets its own branch off `main`. The topic name should be short, descriptive, and kebab-cased:

```bash
# Good branch names
research/roman-coverage
research/trie-radix-vs-standard
research/bigram-smoothing-methods
research/soundex-vs-metaphone

# Bad branch names
research/experiment1
research/test
research/new-idea
```

#### Creating a research branch

```bash
git checkout main
git pull origin main
git checkout -b research/<topic-name>
```

#### Working on a research branch

Commit freely. Research branches do not require clean commit history — the branch itself is the workspace. Use descriptive commit messages, but don't stress about squashing or rebasing.

```bash
# Example commits on a research branch
git commit -m "Add RTGS romanization generation script"
git commit -m "Initial benchmark results: RTGS-only coverage"
git commit -m "Add karaoke data source, rerun benchmarks"
git commit -m "Write summary document"
```

#### Completing a research topic

When the research is complete and the summary is written:

1. Ensure the summary document is at `research/<topic-name>/summary.md` on the branch.
2. Push the branch to the remote.
3. Open a pull request targeting `main`.
4. The PR description should contain a brief overview of findings and link to the summary.

**What gets merged:** Only the summary document (`research/<topic-name>/summary.md`) and any approved additions to shared infrastructure (new benchmark entries, shared utility functions). Experimental notebooks, intermediate data, and scratch code stay on the branch.

**After merge:** The branch is kept (not deleted) so that experimental details remain accessible for reference. Branches can be archived later if the repo grows large.

## Commit Message Conventions

Use short, descriptive messages. Prefix with the stage of research when relevant:

```
[background] Add literature review on trie compression methods
[plan] Define experiment parameters for romanization coverage
[experiment] Run RTGS-only benchmark, record results
[summary] Write findings for romanization coverage study
[infra] Add word-conversion benchmark loader utility
[benchmark] Add 50 compound word test cases
[docs] Update research index with new topic
```

These prefixes are conventions, not enforced by tooling. They help both humans and agents scanning git log understand what happened.

## Pull Request Process

1. **Author** (agent or human) opens a PR from `research/<topic>` → `main`.
2. **PR description** includes: research question, key finding (1-2 sentences), and link to summary.
3. **Maintainer** reviews the summary, verifies benchmark results are reproducible, and checks that conclusions are sound.
4. **Merge** uses a standard merge commit (not squash) to preserve the connection to the research branch.
5. **Post-merge:** Author updates `research/index.md` on `main` with a new entry for the completed topic.

## For Agents: Git Workflow Checklist

When starting a new research topic:

```bash
# 1. Start from latest main
git checkout main
git pull origin main

# 2. Create research branch
git checkout -b research/<topic-name>

# 3. Create your workspace directory
mkdir -p experiments/<topic-name>

# 4. Work through the four research stages
#    (see docs/research-workflow.md)

# 5. Write summary to the research directory
mkdir -p research/<topic-name>
# Write summary.md here

# 6. Commit and push
git add .
git commit -m "[summary] Complete <topic-name> research"
git push origin research/<topic-name>

# 7. Open PR (or notify maintainer to open PR)
```

When updating shared infrastructure on main:

```bash
git checkout main
git pull origin main
# Make changes to docs/, benchmarks/, or src/
git add .
git commit -m "[infra] Description of change"
git push origin main
```
