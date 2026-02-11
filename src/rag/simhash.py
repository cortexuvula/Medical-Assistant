"""
SimHash Implementation for Fuzzy Guideline Deduplication.

Pure Python 64-bit SimHash using built-in hashlib. No external dependencies.

SimHash creates a fingerprint of text that preserves locality:
similar documents produce similar hashes. Two documents with
Hamming distance <= 3 are considered near-duplicates.
"""

import hashlib
import re
from typing import Optional


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words."""
    return re.findall(r'\w+', text.lower())


def _hash_token(token: str) -> int:
    """Hash a token to a 64-bit integer using MD5."""
    digest = hashlib.md5(token.encode('utf-8'), usedforsecurity=False).hexdigest()
    return int(digest[:16], 16)


def compute_simhash(text: str) -> Optional[int]:
    """Compute a 64-bit SimHash fingerprint for the given text.

    Args:
        text: Input text to fingerprint

    Returns:
        64-bit integer SimHash, or None if text is empty
    """
    if not text or not text.strip():
        return None

    tokens = _tokenize(text)
    if not tokens:
        return None

    # Initialize 64-bit vector
    v = [0] * 64

    for token in tokens:
        h = _hash_token(token)
        for i in range(64):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    # Build fingerprint from vector
    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= (1 << i)

    # Convert to signed 64-bit to fit PostgreSQL BIGINT range
    if fingerprint >= (1 << 63):
        fingerprint -= (1 << 64)

    return fingerprint


def hamming_distance(h1: int, h2: int) -> int:
    """Compute Hamming distance between two 64-bit SimHash values.

    Handles both signed (from DB) and unsigned representations.

    Args:
        h1: First SimHash
        h2: Second SimHash

    Returns:
        Number of differing bits (0-64)
    """
    # Mask to 64 bits to handle signed values from PostgreSQL
    return bin((h1 ^ h2) & 0xFFFFFFFFFFFFFFFF).count('1')


def are_near_duplicates(h1: int, h2: int, threshold: int = 3) -> bool:
    """Check if two SimHash values indicate near-duplicate content.

    Args:
        h1: First SimHash
        h2: Second SimHash
        threshold: Maximum Hamming distance to consider as duplicates

    Returns:
        True if documents are near-duplicates
    """
    return hamming_distance(h1, h2) <= threshold
