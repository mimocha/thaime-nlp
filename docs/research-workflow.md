# Research Workflow — thaime-nlp

## Overview

Every research topic in this repo follows a four-stage process. Each stage produces a specific artifact (a markdown document or notebook) that feeds into the next stage. This structure ensures reproducibility, makes results reviewable, and allows work to be resumed across multiple sessions.

```
Stage 1: Background Research    →  hypothesis.md
Stage 2: Experimental Design    →  plan.md
Stage 3: Experimentation        →  results.md (+ code/notebooks)
Stage 4: Summary                →  summary.md (this merges to main)
```

## Session Boundaries

Each stage is designed to fit within a single agent session. When starting a new session for the next stage, the agent reads the artifacts from previous stages as context. This keeps token usage manageable and avoids context degradation.

**Stage 1** and **Stage 2** can sometimes be combined into a single session if the topic is well-scoped and the background research is light. **Stage 3** may span multiple sessions for complex experiments. **Stage 4** should always be its own session to ensure a fresh, focused synthesis.

## File Layout on a Research Branch

All work for a research topic lives in `experiments/<topic-name>/` on the research branch:

```
experiments/<topic-name>/
├── hypothesis.md       # Stage 1 output
├── plan.md             # Stage 2 output
├── results.md          # Stage 3 output
├── notebooks/          # Jupyter notebooks (if applicable)
│   └── *.ipynb
├── scripts/            # Python scripts
│   └── *.py
├── data/               # Topic-specific data (intermediate, not shared)
│   └── ...
└── figures/            # Generated plots and visualizations
    └── *.png
```

The final summary goes in `research/<topic-name>/summary.md` (this is what merges to main).

---

## Stage 1: Background Research

**Goal:** Understand the problem space, review existing approaches, and formulate a clear hypothesis or research question.

**Process:**
1. Review the problem statement (provided by the maintainer or defined in the topic scope).
2. Research existing solutions, algorithms, and relevant literature. Use web search for academic papers, library documentation, and reference implementations.
3. Examine how reference IME projects (kime, librime, Mozc) handle the relevant problem.
4. Document findings and formulate a hypothesis or specific research question.

**Output:** `experiments/<topic-name>/hypothesis.md`

This document should contain:
- **Problem statement** — What specific question are we trying to answer?
- **Background findings** — What do existing approaches look like? What has been tried?
- **Hypothesis / proposed approach** — Based on the background, what approach(es) should we test?
- **Sources** — Links to papers, documentation, or code reviewed.

**Quality checklist:**
- [ ] Problem is specific enough to be testable
- [ ] Background covers at least 2-3 existing approaches or references
- [ ] Hypothesis is falsifiable or approach is concretely comparable against alternatives
- [ ] Sources are cited

---

## Stage 2: Experimental Design

**Goal:** Define exactly what will be tested, how it will be measured, and what success looks like.

**Process:**
1. Read `hypothesis.md` from Stage 1.
2. Define the experimental variables (what changes between runs).
3. Define the evaluation metrics (what numbers will be compared).
4. Identify which benchmark datasets from `benchmarks/` will be used.
5. Specify the implementation plan (what code needs to be written).

**Output:** `experiments/<topic-name>/plan.md`

This document should contain:
- **Variables** — What is being compared? (e.g., "trie variant: standard vs radix vs DAFSA")
- **Metrics** — How will results be measured? (e.g., "precision@1, recall@5, lookup time in ms, memory usage in MB")
- **Datasets** — Which benchmark datasets will be used? Any additional data needed?
- **Procedure** — Step-by-step plan for running the experiments.
- **Success criteria** — What result would lead to adopting or rejecting the hypothesis?
- **Dependencies** — Python packages, data files, or tools required.

**Quality checklist:**
- [ ] Metrics are quantitative and comparable
- [ ] Benchmark datasets are specified (from `benchmarks/`)
- [ ] Procedure is detailed enough that another agent could execute it
- [ ] Success criteria are defined before running experiments (not post-hoc)

---

## Stage 3: Experimentation

**Goal:** Implement the experimental code, run the experiments, and record raw results.

**Process:**
1. Read `hypothesis.md` and `plan.md` from previous stages.
2. Implement the experimental code (scripts or notebooks).
3. Run experiments against the specified benchmark datasets.
4. Record all results — both expected and unexpected.
5. Generate visualizations where helpful.

**Output:** `experiments/<topic-name>/results.md` (plus code in `scripts/` or `notebooks/`)

This document should contain:
- **Setup** — Environment, dependencies installed, any data preprocessing performed.
- **Results** — Tables and/or figures showing experimental outcomes for each variable.
- **Raw numbers** — Exact metric values, not just "X was better than Y."
- **Observations** — Anything surprising or noteworthy during experimentation.
- **Reproducibility** — Commands to rerun the experiments.

**Quality checklist:**
- [ ] All experiments from the plan were executed (or deviations documented)
- [ ] Results include raw numbers, not just qualitative descriptions
- [ ] Code is committed and runnable
- [ ] Benchmark dataset version/state is recorded

**Note for agents:** If experiments are complex and span multiple sessions, append to `results.md` incrementally. Each session should commit its progress before ending.

---

## Stage 4: Summary

**Goal:** Synthesize findings into a concise, actionable summary that can be reviewed and merged to main.

**Process:**
1. Read all previous stage artifacts (`hypothesis.md`, `plan.md`, `results.md`).
2. Write a summary answering: What did we find? What should we do about it?
3. Make a clear recommendation for the main `thaime` engine.
4. Place the summary at `research/<topic-name>/summary.md`.

**Output:** `research/<topic-name>/summary.md`

This document should contain:
- **Title and date**
- **Research question** — One sentence.
- **Approach** — Brief description of what was tested (2-3 sentences).
- **Key findings** — The important results, with numbers.
- **Recommendation** — What should the main thaime engine adopt? Be specific.
- **Limitations** — What wasn't tested, caveats, or areas for follow-up.
- **References** — Links to the experiment branch, key sources.

**Quality checklist:**
- [ ] Summary is self-contained (readable without other artifacts)
- [ ] Findings include specific numbers from the benchmark results
- [ ] Recommendation is concrete and actionable
- [ ] Limitations are honestly stated

---

## For Agents: Starting a New Research Topic

When the maintainer assigns a research topic, follow this sequence:

```
Session 1:
  1. Read CLAUDE.md
  2. Read docs/research-workflow.md (this file)
  3. Read docs/research-template.md (for formatting)
  4. Read docs/benchmarks.md (for available test data)
  5. Create research branch: git checkout -b research/<topic-name>
  6. Create workspace: mkdir -p experiments/<topic-name>
  7. Perform Stage 1 (Background Research)
  8. Write experiments/<topic-name>/hypothesis.md
  9. Commit and push

Session 2:
  1. Read hypothesis.md from previous session
  2. Perform Stage 2 (Experimental Design)
  3. Write experiments/<topic-name>/plan.md
  4. Commit and push

Session 3 (may repeat):
  1. Read hypothesis.md and plan.md
  2. Perform Stage 3 (Experimentation)
  3. Write experiments/<topic-name>/results.md
  4. Commit and push

Session 4:
  1. Read all previous artifacts
  2. Perform Stage 4 (Summary)
  3. Write research/<topic-name>/summary.md
  4. Commit and push
  5. Notify maintainer that the topic is ready for review
```

## For Humans: Starting a Research Topic

Follow the same workflow, but you may choose to combine stages or skip artifacts if working informally. The only hard requirement is that a `summary.md` exists before merging to main.
