"""Auto-classification heuristics for benchmark word entries.

Assigns category (common/compound/ambiguous/variant/edge) and difficulty
(easy/medium/hard) based on word properties.

Extracted from ``pipelines/benchmark-wordconv/02_generate_romanizations.py``.
"""

from __future__ import annotations


# Common function words and particles
_FUNCTION_WORDS = {
    "ที่", "ของ", "ใน", "ได้", "ไม่", "มี", "เป็น", "จะ", "ว่า", "ก็",
    "แต่", "กับ", "ให้", "ไป", "มา", "จาก", "หรือ", "ถ้า", "เพราะ", "ต้อง",
    "คือ", "อยู่", "แล้ว", "ยัง", "ทั้ง", "อย่าง", "ดี", "มาก", "น่า", "ครับ",
    "ค่ะ", "นะ", "คะ", "จ้า", "เลย", "นี้", "นั้น", "ซึ่ง", "เมื่อ", "โดย",
    "กัน", "คน", "วัน", "ปี", "ตอน", "ทำ", "ดู", "รู้", "พูด", "คิด",
    "เรา", "เขา", "ผม", "ฉัน", "ตัว", "หน้า", "ใจ", "ตา", "มือ", "หัว",
}

# Words that commonly have ambiguous romanizations
_KNOWN_AMBIGUOUS_ROMANIZATIONS = {
    "ไม", "ไม่", "ไม้", "ไหม", "ไหม้", "ใหม่",
    "เกา", "เก่า", "เก้า", "เขา", "เข่า", "เข้า", "ขาว", "ข่าว", "ข้าว", "เค้า", "คาว",
    "กัน", "กรรณ", "คัน", "คั่น", "คั้น", "ขัน", "ขั้น",
    "ตา", "ต่า", "ตาร์", "ทา", "ท่า", "ท้า", "ถ้า",
    "ดิ", "ดี", "ติ", "ตี", "ตี่", "ตี้", "ตี๋",
    "สิ", "สี", "สี่", "สี้", "ซิ", "ซี", "ซี้", "ศรี",
    "ใน", "ไหน", "นัย",
    "ชะ", "ช่ะ", "ชา", "ช่า", "ช้า", "ฉา", "ฉ่า",
}


def _has_cluster(romanization: str) -> bool:
    """Check if romanization starts with a consonant cluster."""
    clusters = ["kh", "th", "ph", "ch", "kr", "tr", "pr", "kl", "pl", "bl", "fr", "fl"]
    rom_lower = romanization.lower()
    return any(rom_lower.startswith(c) for c in clusters)


def classify_word(
    thai_word: str,
    romanization: str,
    variant_count: int,
    merged_rank: int,
    syllable_count: int,
) -> tuple[str, str]:
    """Auto-classify a word into category and difficulty.

    Returns:
        (category, difficulty) tuple.
    """
    # Category assignment
    if thai_word in _KNOWN_AMBIGUOUS_ROMANIZATIONS:
        category = "ambiguous"
    elif syllable_count >= 3:
        category = "compound"
    elif variant_count > 10:
        category = "variant"
    elif len(thai_word) <= 2 and syllable_count == 1:
        category = "edge"
    elif thai_word in _FUNCTION_WORDS and merged_rank <= 100:
        category = "common"
    elif merged_rank <= 200:
        category = "common"
    else:
        category = "common"

    # Difficulty assignment
    if syllable_count == 1 and not _has_cluster(romanization):
        difficulty = "easy"
    elif syllable_count <= 2 and variant_count <= 5:
        difficulty = "easy"
    elif syllable_count >= 3 or _has_cluster(romanization):
        difficulty = "medium"
    elif variant_count > 8:
        difficulty = "medium"
    else:
        difficulty = "easy"

    # Override to hard for genuinely tricky cases
    if syllable_count >= 4:
        difficulty = "hard"
    if thai_word in _KNOWN_AMBIGUOUS_ROMANIZATIONS and syllable_count >= 2:
        difficulty = "hard"

    return category, difficulty
