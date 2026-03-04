# Git Workflow — thaime-nlp

## Branching Model

This repo uses a three-tier branching model designed for research workflows:

```
main ─────────────────────────────────────────────────
  │                    ↑ (PR: standard GitHub merge)
  │    summary/roman-coverage ──┘   (clean: only summary.md + approved infra)
  │
  ├── research/roman-coverage       (full experimental branch, kept for reference)
  │
  │                    ↑ (PR: standard GitHub merge)
  │    summary/trie-comparison ─────┘
  │
  ├── research/trie-comparison
  │
  │                    ↑ (PR: standard GitHub merge)
  │    summary/ngram-smoothing ─────┘
  │
  └── research/ngram-smoothing
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
2. Push the research branch to the remote.
3. Create a `summary/<topic-name>` branch from `main` with only the deliverable files (see "Creating a summary branch" below).
4. Open a pull request from `summary/<topic-name>` targeting `main`.
5. The PR description should contain a brief overview of findings and link to the `research/<topic-name>` branch for full detail.

**What gets merged:** Only the summary document (`research/<topic-name>/summary.md`) and any approved additions to shared infrastructure (new benchmark entries, shared utility functions). Experimental notebooks, intermediate data, and scratch code stay on the branch.

**After merge:** The `research/<topic>` branch is kept (not deleted) so that experimental details remain accessible for reference. The `summary/<topic>` branch can be deleted after merge. Branches can be archived later if the repo grows large.

### `summary/<topic-name>` branches

When a research topic is complete, the agent creates a clean `summary/<topic-name>` branch from `main` that contains **only** the files to be merged (summary document and any approved shared infrastructure). This enables standard GitHub merge/squash via the UI, preserving proper merge history.

Summary branches are ephemeral — they exist only to facilitate a clean PR and can be deleted after the PR is merged.

#### Creating a summary branch

```bash
# From the research branch, after all work is complete:
git checkout main
git pull origin main
git checkout -b summary/<topic-name>

# Cherry-pick only the deliverable files from the research branch
git checkout research/<topic-name> -- research/<topic-name>/summary.md

# If the research also produced approved shared infrastructure:
# git checkout research/<topic-name> -- src/utils/new_helper.py benchmarks/new-entries/

git add .
git commit -m "[summary] <topic-name> findings"
git push origin summary/<topic-name>
```

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

1. **Author** creates a `summary/<topic>` branch from `main` containing only the deliverable files (see "Creating a summary branch" above).
2. **Author** opens a PR from `summary/<topic>` → `main`.
3. **PR description** includes: research question, key finding (1-2 sentences), and a link to the `research/<topic>` branch for full experimental detail.
4. **Maintainer** reviews the summary, verifies benchmark results are reproducible (on the research branch), and checks that conclusions are sound.
5. **Maintainer merges via the standard GitHub UI** (merge commit or squash — maintainer's preference). Because the summary branch only contains deliverable files, no experimental artifacts will leak into `main`.
6. **Post-merge:** The `summary/<topic>` branch can be deleted. The `research/<topic>` branch is kept for reference. The author updates `research/index.md` on `main` with a new entry for the completed topic.

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

# 6. Commit and push the research branch
git add .
git commit -m "[summary] Complete <topic-name> research"
git push origin research/<topic-name>

# 7. Create a clean summary branch for the PR
git checkout main
git pull origin main
git checkout -b summary/<topic-name>
git checkout research/<topic-name> -- research/<topic-name>/summary.md
# Also cherry-pick any approved shared infra files if applicable
git add .
git commit -m "[summary] <topic-name> findings"
git push origin summary/<topic-name>

# 8. Open PR from summary/<topic-name> → main (or notify maintainer)
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
