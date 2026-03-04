# Benchmarks — thaime-nlp

## Purpose

Benchmark datasets are the ground truth for evaluating research experiments. They provide standardized, frozen test cases that allow results to be compared across experiments and over time.

**Critical rule:** Benchmark datasets are maintained by the project maintainer. Agents and contributors must not modify existing benchmark entries. If you believe a benchmark needs changes, document your reasoning in your research summary and propose additions — do not edit the benchmark files directly.

## Benchmark Datasets

### 1. Word Conversion (`benchmarks/word-conversion/`)

**What it tests:** Given a Latin (romanized) input, does the system return the correct Thai word in its candidate list?

**Format:** CSV file(s) with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `latin_input` | string | The romanized input the user types |
| `expected_thai` | string | The correct Thai word output |
| `category` | string | Classification of the test case (see below) |
| `difficulty` | string | `easy`, `medium`, or `hard` |
| `notes` | string | Optional context about why this case is included |

**Categories:**
- `common` — Frequently used Thai words with standard romanization
- `ambiguous` — Latin input that could map to multiple Thai words
- `variant` — Non-standard romanization (informal, karaoke-style)
- `compound` — Multi-syllable or compound words
- `similar` — Words that are easily confused (close romanizations mapping to different Thai words)
- `edge` — Edge cases (very short input, unusual consonant clusters, etc.)

**Example entries:**

```csv
latin_input,expected_thai,category,difficulty,notes
sawatdee,สวัสดี,common,easy,Standard greeting
sawasdee,สวัสดี,variant,easy,Common informal romanization
mai,ไม่,ambiguous,medium,"Could also be ไม้, ใหม่, etc."
rongrean,โรงเรียน,compound,medium,School - compound of โรง + เรียน
krungthep,กรุงเทพ,common,medium,Bangkok - consonant cluster
```

**Metrics evaluated against this benchmark:**
- **Precision@1** — Is the top-ranked candidate correct?
- **Precision@k** (k=5, 10) — Is the correct answer in the top k candidates?
- **Coverage** — What percentage of test cases return any candidates at all?

### 2. Segmentation (`benchmarks/segmentation/`)

**What it tests:** Given a multi-word Latin input, does the system correctly segment it into the intended sequence of Thai words?

**Format:** CSV file(s):

| Column | Type | Description |
|--------|------|-------------|
| `latin_input` | string | Multi-word romanized input (no spaces) |
| `expected_segmentation` | string | Pipe-separated Thai words: `word1\|word2\|word3` |
| `category` | string | Test case category |
| `notes` | string | Optional context |

**Example entries:**

```csv
latin_input,expected_segmentation,category,notes
pairongrean,ไป|โรงเรียน,common,Go to school
kinkhao,กิน|ข้าว,common,Eat rice (eat food)
maiaokinkhao,ไม่|อยาก|กิน|ข้าว,multi-word,Don't want to eat
```

**Metrics:**
- **Exact match** — Does the segmentation exactly match the expected output?
- **Word-level F1** — Precision and recall at the individual word level.

### 3. Ranking (`benchmarks/ranking/`)

**What it tests:** Given an ambiguous input with multiple valid Thai interpretations, does the system rank the most likely interpretation highest?

**Format:** CSV file(s):

| Column | Type | Description |
|--------|------|-------------|
| `latin_input` | string | Ambiguous romanized input |
| `context` | string | Previously committed Thai text (empty if none) |
| `expected_top` | string | The Thai word/phrase that should rank first |
| `valid_alternatives` | string | Pipe-separated other valid candidates |
| `notes` | string | Optional context |

**Example entries:**

```csv
latin_input,context,expected_top,valid_alternatives,notes
mai,,ไม่,ไม้|ใหม่|ไหม,No context - most frequent meaning wins
mai,ต้น,ไม้,ไม่|ใหม่|ไหม,After ต้น (tree) - ไม้ (wood) is more likely
kao,,เขา,ข้าว|เก้า|ขาว,No context - pronoun most common
kao,กิน,ข้าว,เขา|เก้า|ขาว,After กิน (eat) - ข้าว (rice) is expected
```

**Metrics:**
- **MRR (Mean Reciprocal Rank)** — Average of 1/rank for the expected top candidate.
- **Context improvement** — Difference in MRR between no-context and with-context conditions.

---

## Using Benchmarks in Experiments

### Loading benchmark data

Use the shared utility functions in `src/utils/` to load benchmarks:

```python
# Example usage (once utilities are implemented)
from src.utils.benchmark import load_word_conversion_benchmark

benchmark = load_word_conversion_benchmark()
# Returns a list of dicts with keys: latin_input, expected_thai, category, difficulty, notes
```

If shared utilities aren't yet available, load the CSV directly:

```python
import csv

def load_benchmark(path):
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

benchmark = load_benchmark('benchmarks/word-conversion/basic.csv')
```

### Reporting benchmark results

When recording results in `results.md`, always include:
1. Which benchmark file(s) were used (exact path)
2. The date/commit of the benchmark (to track if it changes over time)
3. Results broken down by category and difficulty, not just overall
4. The exact command or script used to produce the numbers

### Proposing benchmark additions

If during research you discover important test cases not covered by existing benchmarks:

1. Document the proposed additions in your `results.md` or `summary.md`
2. Include the proposed entries in the same CSV format
3. Explain why these cases are important
4. The maintainer will review and add them to the benchmark on `main` if approved

**Do not add entries directly to benchmark files on your research branch.** If you need additional test cases for your specific experiment, create a separate file in `experiments/<topic-name>/data/` and clearly mark it as experiment-specific, not a benchmark.

---

## Building the Initial Benchmarks

The initial benchmark datasets will be built collaboratively between the maintainer and agents as one of the first research activities. Priority order:

1. **Word conversion (basic)** — Start with ~200-500 curated pairs covering common words, standard romanizations, and known ambiguous cases. This is the minimum needed to begin any romanization research.
2. **Word conversion (extended)** — Expand to ~1000+ pairs with more variant romanizations, compounds, and edge cases.
3. **Segmentation** — Requires the word conversion benchmark to exist first. Start with ~100-200 multi-word sequences.
4. **Ranking** — Requires both word conversion and a functioning language model. Can be built later.

The maintainer will seed the initial benchmarks. Agents can propose additions through the standard research workflow.
