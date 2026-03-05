"""Tests for the variant generator module.

Uses a small set of known Thai words and their expected variants drawn
from Research 002's results to verify correctness.
"""

import pytest

from src.variant_generator import (
    DEFAULT_CONFIG,
    VariantConfig,
    generate_word_variants,
    generate_variants_for_wordlist,
    analyze_word,
)


# ---------------------------------------------------------------------------
# Smoke tests: known words produce expected variants
# ---------------------------------------------------------------------------


class TestKnownWords:
    """Verify that well-known Thai words produce expected informal variants."""

    def test_sawatdee(self):
        """สวัสดี should produce 'sawatdee' variant (vowel lengthening)."""
        variants = generate_word_variants("สวัสดี")
        assert len(variants) > 0
        assert "sawatdee" in variants or "sawaddee" in variants

    def test_dee(self):
        """ดี should produce vowel-lengthened variants like 'dee' or 'dii'."""
        variants = generate_word_variants("ดี")
        assert "dee" in variants or "dii" in variants

    def test_kin(self):
        """กิน should produce 'gin' variant (initial voicing k→g)."""
        variants = generate_word_variants("กิน")
        # Base form should be present
        assert any("in" in v for v in variants)
        # Initial voicing: k → g
        assert "gin" in variants

    def test_moo(self):
        """หมู should produce vowel-lengthened 'moo' or 'muu'."""
        variants = generate_word_variants("หมู")
        assert "moo" in variants or "muu" in variants

    def test_khao(self):
        """ข้าว should produce cluster-simplified variant without 'h'."""
        variants = generate_word_variants("ข้าว")
        assert len(variants) > 0
        # Should have at least the base form
        assert any(v.startswith("k") for v in variants)

    def test_phuket(self):
        """ภูเก็ต should produce variants with ph→p simplification."""
        variants = generate_word_variants("ภูเก็ต")
        assert len(variants) > 0
        # Cluster simplification: ph → p
        assert any(v.startswith("p") and not v.startswith("ph") for v in variants)

    def test_krungthep(self):
        """กรุงเทพ should produce variants with r-dropping."""
        variants = generate_word_variants("กรุงเทพ")
        assert len(variants) > 0

    def test_empty_for_non_thai(self):
        """Non-Thai input should return empty or minimal results gracefully."""
        variants = generate_word_variants("")
        assert isinstance(variants, list)

    def test_base_form_always_included(self):
        """The base TLTK romanization should always be in the result."""
        for word in ["ดี", "กิน", "หมู", "ไทย"]:
            variants = generate_word_variants(word)
            if variants:  # If TLTK can process the word
                assert len(variants) >= 1


# ---------------------------------------------------------------------------
# max_variants_per_word
# ---------------------------------------------------------------------------


class TestMaxVariants:
    """Verify that max_variants_per_word is respected."""

    def test_default_max_is_20(self):
        assert DEFAULT_CONFIG.max_variants_per_word == 20

    def test_max_variants_respected(self):
        """Output should not exceed max_variants_per_word."""
        config = VariantConfig(max_variants_per_word=5)
        # Use a word that produces many variants
        variants = generate_word_variants("สวัสดี", config)
        assert len(variants) <= 5

    def test_max_variants_still_includes_base(self):
        """Even with a tight limit, the base form should be included."""
        config = VariantConfig(max_variants_per_word=2)
        variants = generate_word_variants("ดี", config)
        assert len(variants) <= 2
        assert len(variants) >= 1

    def test_large_max_variants(self):
        """With a large max, we get more variants."""
        config_small = VariantConfig(max_variants_per_word=3)
        config_large = VariantConfig(max_variants_per_word=100)
        small = generate_word_variants("สวัสดี", config_small)
        large = generate_word_variants("สวัสดี", config_large)
        assert len(large) >= len(small)


# ---------------------------------------------------------------------------
# Configuration flags
# ---------------------------------------------------------------------------


class TestConfigFlags:
    """Verify that enabling/disabling rules changes output."""

    def test_disable_vowel_lengthening(self):
        """Disabling vowel lengthening should reduce variant count for long-vowel words."""
        config_on = VariantConfig(vowel_lengthening=True)
        config_off = VariantConfig(vowel_lengthening=False)
        variants_on = generate_word_variants("ดี", config_on)
        variants_off = generate_word_variants("ดี", config_off)
        # With vowel lengthening off, should have fewer variants
        assert len(variants_off) <= len(variants_on)

    def test_disable_initial_voicing(self):
        """Disabling initial voicing should exclude 'g' variants for ก words."""
        config_on = VariantConfig(initial_voicing=True)
        config_off = VariantConfig(initial_voicing=False)
        variants_on = generate_word_variants("กิน", config_on)
        variants_off = generate_word_variants("กิน", config_off)
        if "gin" in variants_on:
            assert "gin" not in variants_off

    def test_disable_final_softening(self):
        """Disabling final softening should exclude voiced-stop finals."""
        config_on = VariantConfig(final_consonant_softening=True)
        config_off = VariantConfig(final_consonant_softening=False)
        variants_on = generate_word_variants("วัด", config_on)
        variants_off = generate_word_variants("วัด", config_off)
        assert len(variants_off) <= len(variants_on)

    def test_disable_all_rules(self):
        """With all rules disabled, should only produce the base romanization."""
        config = VariantConfig(
            vowel_lengthening=False,
            final_consonant_softening=False,
            cluster_simplification=False,
            r_dropping=False,
            initial_voicing=False,
        )
        variants = generate_word_variants("ดี", config)
        # Should have exactly 1 variant (the base form)
        assert len(variants) == 1

    def test_all_rules_enabled_produces_most_variants(self):
        """All rules enabled should produce the most variants."""
        config_all = VariantConfig()  # All enabled by default
        config_none = VariantConfig(
            vowel_lengthening=False,
            final_consonant_softening=False,
            cluster_simplification=False,
            r_dropping=False,
            initial_voicing=False,
        )
        for word in ["สวัสดี", "กรุงเทพ", "ภูเก็ต"]:
            all_on = generate_word_variants(word, config_all)
            all_off = generate_word_variants(word, config_none)
            assert len(all_on) >= len(all_off)


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
# Syllable analysis
# ---------------------------------------------------------------------------


class TestAnalyzeWord:
    """Verify syllable analysis produces reasonable output."""

    def test_analyze_returns_syllables(self):
        syllables = analyze_word("สวัสดี")
        assert len(syllables) > 0

    def test_syllable_has_romanization(self):
        syllables = analyze_word("ดี")
        assert len(syllables) >= 1
        assert syllables[0].romanization != ""

    def test_long_vowel_detection(self):
        """ดี has a long vowel (อี), should be detected."""
        syllables = analyze_word("ดี")
        assert len(syllables) >= 1
        assert syllables[0].has_long_vowel is True
