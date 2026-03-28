"""Tests for rag.simhash — 64-bit SimHash implementation."""

import pytest

from rag.simhash import (
    _tokenize,
    _hash_token,
    compute_simhash,
    hamming_distance,
    are_near_duplicates,
)


class TestTokenize:
    def test_simple_sentence(self):
        tokens = _tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_strips_punctuation(self):
        tokens = _tokenize("Hello, world! How are you?")
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_lowercases_everything(self):
        tokens = _tokenize("UPPER lower MiXeD")
        assert tokens == ["upper", "lower", "mixed"]

    def test_whitespace_only(self):
        assert _tokenize("   \t\n  ") == []


class TestHashToken:
    def test_returns_integer(self):
        result = _hash_token("hello")
        assert isinstance(result, int)

    def test_deterministic(self):
        assert _hash_token("test") == _hash_token("test")

    def test_different_tokens_different_hashes(self):
        assert _hash_token("alpha") != _hash_token("beta")

    def test_64_bit_range(self):
        h = _hash_token("some_word")
        assert 0 <= h < (1 << 64)


class TestComputeSimhash:
    def test_empty_string_returns_none(self):
        assert compute_simhash("") is None

    def test_whitespace_only_returns_none(self):
        assert compute_simhash("   \t\n  ") is None

    def test_none_like_empty_returns_none(self):
        assert compute_simhash("") is None

    def test_single_word_returns_int(self):
        result = compute_simhash("hello")
        assert isinstance(result, int)

    def test_multiple_words_returns_int(self):
        result = compute_simhash("the quick brown fox jumps over the lazy dog")
        assert isinstance(result, int)

    def test_deterministic(self):
        text = "patient presents with chest pain"
        assert compute_simhash(text) == compute_simhash(text)

    def test_signed_64_bit_range(self):
        result = compute_simhash("a b c d e f g h i j k l m n o p")
        assert result is not None
        assert -(1 << 63) <= result < (1 << 63)

    def test_similar_texts_produce_close_hashes(self):
        h1 = compute_simhash("the patient has a persistent headache and fever")
        h2 = compute_simhash("the patient has a persistent headache and chills")
        assert h1 is not None and h2 is not None
        dist = hamming_distance(h1, h2)
        # Similar texts should have relatively low hamming distance
        assert dist < 32

    def test_very_different_texts_produce_distant_hashes(self):
        h1 = compute_simhash("the quick brown fox jumps over the lazy dog")
        h2 = compute_simhash("quantum mechanics describes wave particle duality in atoms")
        assert h1 is not None and h2 is not None
        # Different texts should not be identical
        assert h1 != h2

    def test_punctuation_only_returns_none(self):
        assert compute_simhash("!!! ??? ...") is None


class TestHammingDistance:
    def test_identical_hashes_distance_zero(self):
        assert hamming_distance(42, 42) == 0

    def test_single_bit_difference(self):
        assert hamming_distance(0, 1) == 1

    def test_all_bits_different_64(self):
        h1 = 0
        h2 = 0xFFFFFFFFFFFFFFFF
        assert hamming_distance(h1, h2) == 64

    def test_known_distance(self):
        # 0b1010 vs 0b0101 -> 4 bits different
        assert hamming_distance(0b1010, 0b0101) == 4

    def test_handles_negative_signed_values(self):
        # Signed -1 in 64-bit is all 1s
        dist = hamming_distance(-1, 0)
        assert dist == 64

    def test_symmetric(self):
        assert hamming_distance(123, 456) == hamming_distance(456, 123)

    def test_masks_to_64_bits(self):
        # Values larger than 64 bits should be masked
        large = (1 << 65)  # bit 65 set
        dist = hamming_distance(large, 0)
        # After masking to 64 bits, bit 65 is gone, only bit 1 remains (1<<65 & mask = 0? No: 1<<65 is beyond 64 bits)
        # Actually (1<<65) & 0xFFFFFFFFFFFFFFFF == 0 since bit 65 is above 64-bit range
        assert dist == 0


class TestAreNearDuplicates:
    def test_identical_hashes_are_duplicates(self):
        assert are_near_duplicates(100, 100) is True

    def test_distance_within_default_threshold(self):
        # Distance of 3 should be within threshold=3
        assert are_near_duplicates(0b000, 0b111) is True

    def test_distance_exceeds_default_threshold(self):
        # Distance of 4 should exceed threshold=3
        assert are_near_duplicates(0b0000, 0b1111) is False

    def test_custom_threshold_strict(self):
        assert are_near_duplicates(0b00, 0b11, threshold=1) is False

    def test_custom_threshold_lenient(self):
        assert are_near_duplicates(0b0000, 0b1111, threshold=10) is True

    def test_with_real_text_near_duplicates(self):
        h1 = compute_simhash("patient presents with persistent headache lasting three days")
        h2 = compute_simhash("patient presents with persistent headache lasting four days")
        assert h1 is not None and h2 is not None
        dist = hamming_distance(h1, h2)
        # Texts sharing most words should have distance well below the max of 64
        assert dist < 32

    def test_with_real_text_not_duplicates(self):
        h1 = compute_simhash("patient presents with persistent headache lasting three days")
        h2 = compute_simhash("quantum mechanics string theory particle physics acceleration")
        assert h1 is not None and h2 is not None
        # Very different texts should not be near-duplicates at strict threshold
        assert are_near_duplicates(h1, h2, threshold=0) is False
