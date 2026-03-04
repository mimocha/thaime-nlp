# Corpora — thaime-nlp

## Overview

This directory contains Thai text corpora used for NLP research in the THAIME project. Raw corpus data is **not version controlled** — it is downloaded on-demand via scripts and stored in the gitignored `raw/` subdirectory.

Corpora were selected from the [thaime-candidate](https://github.com/mimocha/thaime-candidate) research repo to cover three registers of Thai writing:

| Register | Corpora |
|----------|---------|
| **Formal** | Prachathai 67K (news), Thai Wikipedia (encyclopedia) |
| **Informal** | Wisesight (social media), Wongnai (restaurant reviews) |
| **Mixed** | HSE Thai Corpus (web-scraped, mostly news) |

## Directory Structure

```
data/corpora/
├── README.md           # This file (tracked in git)
├── raw/                # Downloaded corpus data (gitignored)
│   ├── prachathai/     # Prachathai 67K news articles
│   ├── wisesight/      # Wisesight sentiment text files
│   ├── wongnai/        # Wongnai restaurant reviews
│   ├── thwiki/         # Thai Wikipedia XML dump
│   └── hse/            # HSE Thai Corpus
└── .gitkeep
```

## Downloading Corpora

Each corpus can be downloaded independently. Use the download script:

```bash
# List available corpora
python -m src.data.download --list

# Check download status
python -m src.data.download --status

# Download individual corpora
python -m src.data.download prachathai
python -m src.data.download wisesight
python -m src.data.download wongnai
python -m src.data.download thwiki       # Large: ~500 MB download
python -m src.data.download hse          # May require manual download

# Download multiple at once
python -m src.data.download prachathai wisesight wongnai

# Download all corpora
python -m src.data.download --all

# Force re-download (overwrites existing)
python -m src.data.download prachathai --force
```

Or use the Python API:

```python
from src.data import download_corpus, list_corpora

list_corpora()
download_corpus("prachathai")
download_corpus("all")
```

## Corpus Details

### 1. Prachathai 67K

| Field | Value |
|-------|-------|
| **Name** | `prachathai` |
| **Description** | 67,889 news articles from Prachathai.com (left-leaning Thai news) |
| **Category** | Formal (news articles) |
| **Size** | ~50 MB download |
| **License** | Apache-2.0 |
| **Source** | [PyThaiNLP/prachathai-67k](https://github.com/PyThaiNLP/prachathai-67k) |
| **Format** | JSON files with `body_text` field |

### 2. Wisesight Sentiment

| Field | Value |
|-------|-------|
| **Name** | `wisesight` |
| **Description** | 26,737 Thai social media messages with sentiment labels |
| **Category** | Informal (social media) |
| **Size** | ~5 MB download |
| **License** | CC0-1.0 (public domain) |
| **Source** | [PyThaiNLP/wisesight-sentiment](https://github.com/PyThaiNLP/wisesight-sentiment) |
| **Format** | 4 text files (pos.txt, neg.txt, neu.txt, q.txt), one message per line |

### 3. Wongnai Reviews

| Field | Value |
|-------|-------|
| **Name** | `wongnai` |
| **Description** | Thai restaurant reviews with star ratings (1-5) |
| **Category** | Informal (internet reviews) |
| **Size** | ~60 MB download |
| **License** | LGPL-3.0 |
| **Source** | [wongnai/wongnai-corpus](https://github.com/wongnai/wongnai-corpus) |
| **Format** | Review text with ratings |

### 4. Thai Wikipedia

| Field | Value |
|-------|-------|
| **Name** | `thwiki` |
| **Description** | Complete dump of Thai-language Wikipedia articles |
| **Category** | Formal (encyclopedia) |
| **Size** | ~500 MB compressed, ~1.5 GB uncompressed |
| **License** | CC-BY-SA-3.0 |
| **Source** | [Wikimedia Dumps](https://dumps.wikimedia.org/thwiki/) |
| **Format** | MediaWiki XML dump (bz2 compressed) |

**Note:** The Wikipedia dump is large and requires XML parsing. Consider using `mwparserfromhell` or `wikitextparser` to extract clean article text.

### 5. HSE Thai Corpus

| Field | Value |
|-------|-------|
| **Name** | `hse` |
| **Description** | ~50 million tokens from Thai websites (mostly news) |
| **Category** | Mixed (web text) |
| **Size** | ~200 MB compressed |
| **License** | Research use |
| **Source** | [web-corpora.net](https://web-corpora.net/ThaiCorpus/search/) |
| **Format** | Text files |

**Note:** The HSE corpus may require manual download if the automated script fails. Visit the source URL for the latest access instructions.

## Why Not Version Control the Raw Data?

Raw corpora can be **hundreds of megabytes to gigabytes** in size. Storing them in git would:
- Bloat the repository size permanently (git stores full history)
- Make cloning slow for all contributors
- Duplicate data already available from canonical sources

Instead, we:
1. **Track download scripts** in git (reproducible)
2. **Store raw data locally** in gitignored directories
3. **Track processed outputs** (word frequency tables, dictionaries) in git — these are small

## Adding a New Corpus

1. Add a `CorpusInfo` entry in `src/data/registry.py`
2. Add a download handler function in `src/data/download.py`
3. Register the handler in the `_DOWNLOAD_HANDLERS` dict
4. Update this README with the corpus details
5. Test with `python -m src.data.download <name>`
