# Research Templates — thaime-nlp

This document contains copy-paste templates for each research artifact. When creating a new artifact, copy the relevant template and fill it in.

---

## hypothesis.md Template

```markdown
# [Topic Name]: Background Research & Hypothesis

**Topic:** research/<topic-name>
**Date:** YYYY-MM-DD
**Author:** [agent / human name]

## Problem Statement

[What specific question are we trying to answer? Why does it matter for THAIME?]

## Background Research

### [Subtopic or Approach 1]

[Description of existing approach, how it works, strengths and weaknesses.]

Source: [URL or citation]

### [Subtopic or Approach 2]

[...]

### Relevance to THAIME

[How do these existing approaches inform our problem? What is directly applicable vs. what needs adaptation for Thai?]

## Hypothesis / Proposed Approach

[Based on the background research, what do we believe will work best? What specific approaches should we test?]

## Sources

- [Source 1: title, URL]
- [Source 2: title, URL]
- [...]
```

---

## plan.md Template

```markdown
# [Topic Name]: Experimental Plan

**Topic:** research/<topic-name>
**Date:** YYYY-MM-DD
**Author:** [agent / human name]
**Depends on:** hypothesis.md

## Experimental Variables

| Variable | Values | Description |
|----------|--------|-------------|
| [var1] | [val_a, val_b, val_c] | [What this variable controls] |
| [var2] | [val_x, val_y] | [...] |

## Evaluation Metrics

| Metric | Description | How Measured |
|--------|-------------|--------------|
| [metric1] | [What it tells us] | [Formula or method] |
| [metric2] | [...] | [...] |

## Datasets

- **Benchmark used:** [Name from benchmarks/ directory]
- **Additional data:** [Any extra data needed, with source]
- **Preprocessing:** [Any transformations applied to data before experiments]

## Procedure

1. [Step 1: e.g., "Load benchmark dataset from benchmarks/word-conversion/"]
2. [Step 2: e.g., "Build trie variant A using RTGS romanizations only"]
3. [Step 3: e.g., "Run benchmark queries, record precision@1 and lookup time"]
4. [Step 4: e.g., "Repeat for trie variant B"]
5. [Step 5: e.g., "Compare results across variants"]

## Success Criteria

[What result would lead us to adopt approach A over B? Be specific about thresholds or relative performance.]

## Dependencies

```
pip install [package1] [package2] ...
```

## Estimated Effort

[Rough estimate: how many experiment runs, how long each takes, total compute time expected.]
```

---

## results.md Template

```markdown
# [Topic Name]: Experimental Results

**Topic:** research/<topic-name>
**Date:** YYYY-MM-DD
**Author:** [agent / human name]
**Depends on:** hypothesis.md, plan.md

## Setup

- **Python version:** [e.g., 3.11]
- **Key dependencies:** [packages and versions]
- **Hardware:** [if relevant to timing benchmarks]
- **Data:** [benchmark dataset version/date, any preprocessing notes]

## Results

### [Experiment 1 Name]

[Description of what was run.]

| [Variable] | [Metric 1] | [Metric 2] | [Metric 3] |
|------------|------------|------------|------------|
| [val_a] | [number] | [number] | [number] |
| [val_b] | [number] | [number] | [number] |
| [val_c] | [number] | [number] | [number] |

[Figure reference if applicable: see figures/experiment1.png]

### [Experiment 2 Name]

[...]

## Observations

- [Anything surprising or noteworthy]
- [Edge cases encountered]
- [Deviations from the plan and why]

## Reproducibility

To rerun these experiments:

```bash
cd experiments/<topic-name>
pip install -r requirements.txt  # or inline pip installs
python scripts/run_experiment.py
```

## Raw Data

[Location of raw output files, if any: e.g., experiments/<topic-name>/data/results.csv]
```

---

## summary.md Template

```markdown
# [Topic Name]

**Date:** YYYY-MM-DD
**Author:** [agent / human name]
**Branch:** research/<topic-name>
**Status:** [Complete / Pending Review]

## Research Question

[One sentence stating the question.]

## Approach

[2-3 sentences describing what was tested and how.]

## Key Findings

[Bullet points with specific numbers from benchmark results.]

- Finding 1: [specific result with number]
- Finding 2: [specific result with number]
- Finding 3: [specific result with number]

## Recommendation

[What should the main thaime engine adopt? Be concrete.]

## Limitations

- [What wasn't tested]
- [Caveats on the results]
- [Suggested follow-up research]

## References

- Experiment branch: `research/<topic-name>`
- [Key external sources used]
```

---

## research/index.md Template

The research index on `main` uses this format. Add a new entry when merging a completed topic.

```markdown
# Research Index — thaime-nlp

## Completed Research

| # | Topic | Date | Key Finding | Summary |
|---|-------|------|-------------|---------|
| 1 | [Topic Name] | YYYY-MM-DD | [One-line finding] | [research/topic-name/summary.md](research/topic-name/summary.md) |
| 2 | ... | ... | ... | ... |

## In Progress

| Topic | Branch | Stage | Started |
|-------|--------|-------|---------|
| [Topic Name] | `research/topic-name` | [1-4] | YYYY-MM-DD |
```
