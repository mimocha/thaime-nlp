"""Wikitext markup cleanup utilities.

Provides ``clean_wikitext()`` and ``detect_mediawiki_namespace()`` for
processing Thai Wikipedia XML dumps.

Extracted from ``pipelines/trie/wordlist.py``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Wikitext cleanup patterns (compiled once)
# ---------------------------------------------------------------------------

_WIKI_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_WIKI_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")  # non-nested templates
_WIKI_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/>]*/>", re.DOTALL)
_WIKI_HTML = re.compile(r"<[^>]+>")
_WIKI_LINK = re.compile(r"\[\[[^\]]*?\|([^\]]+)\]\]")  # [[target|display]]
_WIKI_LINK_SIMPLE = re.compile(r"\[\[([^\]|]+)\]\]")  # [[target]]
_WIKI_EXT_LINK = re.compile(r"\[https?://[^\]]*\]")
_WIKI_TABLE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_WIKI_HEADER = re.compile(r"^=+.*?=+$", re.MULTILINE)
_WIKI_CATEGORY = re.compile(r"\[\[(?:หมวดหมู่|Category):[^\]]+\]\]")
_WIKI_FILE = re.compile(r"\[\[(?:ไฟล์|File|Image):[^\]]+\]\]")
_WIKI_FORMATTING = re.compile(r"'{2,5}")
_WIKI_BULLET = re.compile(r"^[*#:;]+\s*", re.MULTILINE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_mediawiki_namespace(fileobj) -> str:
    """Detect the MediaWiki XML namespace from the root element.

    Reads the first few elements to find the namespace URI, then returns
    it in {uri} format. Falls back to export-0.10 if detection fails.
    """
    fallback = "{http://www.mediawiki.org/xml/export-0.10/}"
    try:
        for event, elem in ET.iterparse(fileobj, events=("start",)):
            # The root <mediawiki> element carries the namespace
            tag = elem.tag
            if tag.startswith("{"):
                ns = tag[: tag.index("}") + 1]
                return ns
            break
    except ET.ParseError:
        pass
    return fallback


def clean_wikitext(text: str) -> str:
    """Remove wikitext markup to extract plain text.

    This is a lightweight cleanup — not a full parser. Good enough for
    vocabulary extraction where some noise is acceptable.
    """
    # Remove structural elements first
    text = _WIKI_COMMENT.sub("", text)
    text = _WIKI_TABLE.sub("", text)
    text = _WIKI_REF.sub("", text)
    text = _WIKI_CATEGORY.sub("", text)
    text = _WIKI_FILE.sub("", text)

    # Remove templates (iterate for nested templates)
    for _ in range(5):
        new_text = _WIKI_TEMPLATE.sub("", text)
        if new_text == text:
            break
        text = new_text

    # Convert links to display text
    text = _WIKI_LINK.sub(r"\1", text)
    text = _WIKI_LINK_SIMPLE.sub(r"\1", text)
    text = _WIKI_EXT_LINK.sub("", text)

    # Remove HTML and formatting
    text = _WIKI_HTML.sub("", text)
    text = _WIKI_FORMATTING.sub("", text)
    text = _WIKI_HEADER.sub("", text)
    text = _WIKI_BULLET.sub("", text)

    return text
