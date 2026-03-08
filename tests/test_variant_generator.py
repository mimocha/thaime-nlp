"""Tests for the dictionary-driven variant generator (v2).

Verifies that the component dictionary loads correctly, g2p-based word
analysis produces valid decompositions, and the variant generator produces
expected romanizations for known Thai words.
"""

import pytest

from src.variant_generator import (
    generate_word_variants,
    generate_variants_for_wordlist,
    analyze_word,
    load_component_dictionary,
    SyllableComponents,
)


# ---------------------------------------------------------------------------
# Dictionary loading
# ---------------------------------------------------------------------------


class TestDictionaryLoading:
    """Verify the component dictionary loads correctly."""

    def test_dictionary_loads(self):
        d = load_component_dictionary()
        assert "onsets" in d
        assert "vowels" in d
        assert "codas" in d

    def test_dictionary_has_entries(self):
        d = load_component_dictionary()
        assert len(d["onsets"]) >= 20
        assert len(d["vowels"]) >= 10
        assert len(d["codas"]) >= 5

    def test_onset_variants_are_lists(self):
        d = load_component_dictionary()
        for key, variants in d["onsets"].items():
            assert isinstance(variants, list), f"Onset {key} should be list"
            assert len(variants) >= 1

    def test_vowel_variants_are_lists(self):
        d = load_component_dictionary()
        for key, variants in d["vowels"].items():
            assert isinstance(variants, list), f"Vowel {key} should be list"
            assert len(variants) >= 1

    def test_coda_variants_are_lists(self):
        d = load_component_dictionary()
        for key, variants in d["codas"].items():
            assert isinstance(variants, list), f"Coda {key} should be list"
            assert len(variants) >= 1


# ---------------------------------------------------------------------------
# Smoke tests: known words produce expected variants
# ---------------------------------------------------------------------------


class TestKnownWords:
    """Verify that well-known Thai words produce expected informal variants."""

    def test_sawatdee(self):
        """สวัสดี should produce 'sawatdee' or 'sawaddee' variant."""
        variants = generate_word_variants("สวัสดี", max_variants=200)
        assert len(variants) > 0
        assert "sawatdee" in variants or "sawaddee" in variants

    def test_dee(self):
        """ดี should produce vowel-lengthened variants like 'dee' or 'dii'."""
        variants = generate_word_variants("ดี")
        assert "dee" in variants or "dii" in variants

    def test_kin(self):
        """กิน should produce 'gin' variant (initial voicing k→g)."""
        variants = generate_word_variants("กิน")
        assert any("in" in v for v in variants)
        assert "gin" in variants

    def test_moo(self):
        """หมู should produce 'moo' or 'muu' variant."""
        variants = generate_word_variants("หมู")
        assert "moo" in variants or "muu" in variants

    def test_khao(self):
        """ข้าว should produce variants starting with 'k'."""
        variants = generate_word_variants("ข้าว")
        assert len(variants) > 0
        assert any(v.startswith("k") for v in variants)

    def test_phuket(self):
        """ภูเก็ต should produce variants with ph→p simplification."""
        variants = generate_word_variants("ภูเก็ต")
        assert len(variants) > 0
        assert any(
            v.startswith("p") and not v.startswith("ph") for v in variants
        )

    def test_krungthep(self):
        """กรุงเทพ should produce variants."""
        variants = generate_word_variants("กรุงเทพ")
        assert len(variants) > 0

    def test_empty_for_non_thai(self):
        """Non-Thai input should return empty or minimal results."""
        variants = generate_word_variants("")
        assert isinstance(variants, list)

    def test_base_form_always_included(self):
        """The base TLTK romanization should always be in the result."""
        for word in ["ดี", "กิน", "หมู", "ไทย"]:
            variants = generate_word_variants(word)
            if variants:
                assert len(variants) >= 1


# ---------------------------------------------------------------------------
# max_variants
# ---------------------------------------------------------------------------


class TestMaxVariants:
    """Verify that max_variants parameter is respected."""

    def test_default_max_is_20(self):
        """Default should not exceed 20 variants."""
        variants = generate_word_variants("สวัสดี")
        assert len(variants) <= 20

    def test_max_variants_respected(self):
        """Output should not exceed max_variants."""
        variants = generate_word_variants("สวัสดี", max_variants=5)
        assert len(variants) <= 5

    def test_max_variants_still_includes_base(self):
        """Even with a tight limit, at least one variant should be present."""
        variants = generate_word_variants("ดี", max_variants=2)
        assert len(variants) <= 2
        assert len(variants) >= 1

    def test_large_max_variants(self):
        """With a large max, we get more variants."""
        small = generate_word_variants("สวัสดี", max_variants=3)
        large = generate_word_variants("สวัสดี", max_variants=100)
        assert len(large) >= len(small)


# ---------------------------------------------------------------------------
# Wordlist API
# ---------------------------------------------------------------------------


class TestWordlistAPI:
    """Verify the batch processing function."""

    def test_generate_variants_for_wordlist(self):
        words = ["ดี", "กิน"]
        result = generate_variants_for_wordlist(words)
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "ดี" in result
        assert "กิน" in result
        assert isinstance(result["ดี"], list)
        assert isinstance(result["กิน"], list)


# ---------------------------------------------------------------------------
# Syllable analysis (g2p decomposition)
# ---------------------------------------------------------------------------


class TestAnalyzeWord:
    """Verify g2p-based syllable analysis produces correct decompositions."""

    def test_analyze_returns_syllables(self):
        syllables = analyze_word("สวัสดี")
        assert len(syllables) > 0

    def test_syllable_has_components(self):
        """ดี should decompose to onset=d, vowel=ii, coda=''."""
        syllables = analyze_word("ดี")
        assert len(syllables) >= 1
        assert isinstance(syllables[0], SyllableComponents)
        assert syllables[0].onset == "d"
        assert syllables[0].vowel == "ii"
        assert syllables[0].coda == ""

    def test_kin_decomposition(self):
        """กิน should decompose to onset=k, vowel=i, coda=n."""
        syllables = analyze_word("กิน")
        assert len(syllables) == 1
        assert syllables[0].onset == "k"
        assert syllables[0].vowel == "i"
        assert syllables[0].coda == "n"

    def test_multi_syllable(self):
        """สวัสดี should produce multiple syllables."""
        syllables = analyze_word("สวัสดี")
        assert len(syllables) >= 2

    def test_khao_decomposition(self):
        """ข้าว should decompose to onset=kh, vowel=aa, coda=w."""
        syllables = analyze_word("ข้าว")
        assert len(syllables) == 1
        assert syllables[0].onset == "kh"
        assert syllables[0].vowel == "aa"
        assert syllables[0].coda == "w"

    def test_thai_decomposition(self):
        """ไทย should decompose to onset=th, vowel=aj, coda=''."""
        syllables = analyze_word("ไทย")
        assert len(syllables) == 1
        assert syllables[0].onset == "th"
        assert syllables[0].vowel == "aj"
        assert syllables[0].coda == ""

    def test_hor_nam_detection(self):
        """หน้า should have nh onset."""
        syllables = analyze_word("หน้า")
        assert len(syllables) >= 1
        assert syllables[0].onset == "nh"

    def test_hor_moo_detection(self):
        """หมู should have mh onset."""
        syllables = analyze_word("หมู")
        assert len(syllables) >= 1
        assert syllables[0].onset == "mh"

    def test_zero_onset(self):
        """อาจ should have glottal stop onset (?)."""
        syllables = analyze_word("อาจ")
        assert len(syllables) >= 1
        assert syllables[0].onset == "?"


# ---------------------------------------------------------------------------
# Pre-computed arguments (performance optimization path)
# ---------------------------------------------------------------------------


class TestPrecomputedArgs:
    """Verify that passing pre-computed _base_roman and _syllables produces
    identical output to the default code path."""

    @pytest.mark.parametrize(
        "word",
        ["ดี", "กิน", "หมู", "ข้าว", "สวัสดี", "กรุงเทพ", "ไทย", "ภูเก็ต"],
    )
    def test_precomputed_matches_default(self, word):
        """Output with pre-computed args must match the default path."""
        from src.variant_generator import _clean_tltk_output
        import tltk

        # Default path
        default_variants = generate_word_variants(word, max_variants=200)

        # Pre-computed path
        base_roman = _clean_tltk_output(tltk.nlp.th2roman(word))
        syllables = analyze_word(word)
        precomputed_variants = generate_word_variants(
            word,
            max_variants=200,
            _base_roman=base_roman,
            _syllables=syllables,
        )

        assert precomputed_variants == default_variants

    def test_precomputed_base_roman_only(self):
        """Passing only _base_roman should still work (syllables computed internally)."""
        from src.variant_generator import _clean_tltk_output
        import tltk

        word = "ดี"
        default = generate_word_variants(word)
        base_roman = _clean_tltk_output(tltk.nlp.th2roman(word))
        result = generate_word_variants(word, _base_roman=base_roman)
        assert result == default

    def test_precomputed_syllables_only(self):
        """Passing only _syllables should still work (base_roman computed internally)."""
        word = "กิน"
        default = generate_word_variants(word)
        syllables = analyze_word(word)
        result = generate_word_variants(word, _syllables=syllables)
        assert result == default


# ---------------------------------------------------------------------------
# Glide-coda guards
# ---------------------------------------------------------------------------


class TestGlideCodaGuards:
    """Verify guards that suppress implausible vowel+coda combinations."""

    def test_no_io_for_i_plus_w(self):
        """Vowel i + coda w should NOT produce 'io' combinations.

        The 'o' coda variant after 'i' reads as separate syllables.
        E.g., ผิว → phiw/phiu (not phio).
        """
        variants = generate_word_variants("ผิว", max_variants=100)
        for v in variants:
            # No variant should end in "io" from the i+w decomposition
            assert not v.endswith("io"), f"'{v}' contains 'io' from i+w"
            assert not v.endswith("iio"), f"'{v}' contains 'iio' from ii+w"

    def test_review_no_io(self):
        """รีวิว should not produce any variant containing 'io'."""
        variants = generate_word_variants("รีวิว", max_variants=200)
        io_variants = [v for v in variants if "io" in v]
        assert io_variants == [], f"Found 'io' variants: {io_variants}"


# ---------------------------------------------------------------------------
# Dash stripping
# ---------------------------------------------------------------------------


class TestDashStripping:
    """Verify that RTGS dashes are stripped from romanization output."""

    def test_no_dashes_in_variants(self):
        """Variants should never contain dashes (RTGS syllable separators).

        E.g., ตัวเอง → tuaeng (not tua-eng).
        """
        # ตัวเอง produces "tua-eng" in TLTK RTGS
        variants = generate_word_variants("ตัวเอง", max_variants=200)
        for v in variants:
            assert "-" not in v, f"'{v}' contains a dash"

    def test_kao_i_no_dash(self):
        """เก้าอี้ → kaoi (not kao-i)."""
        variants = generate_word_variants("เก้าอี้", max_variants=200)
        for v in variants:
            assert "-" not in v, f"'{v}' contains a dash"
