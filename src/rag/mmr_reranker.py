"""
Maximal Marginal Relevance (MMR) reranking for RAG system.

Provides result diversity by selecting documents that are both
relevant to the query and diverse from already-selected documents.

MMR formula: MMR = λ * relevance - (1-λ) * max_similarity_to_selected
"""

import math
from typing import Optional

from rag.models import HybridSearchResult
from rag.search_config import SearchQualityConfig, get_search_quality_config
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class MMRReranker:
    """Applies Maximal Marginal Relevance reranking for diverse results."""

    def __init__(self, config: Optional[SearchQualityConfig] = None):
        """Initialize MMR reranker.

        Args:
            config: Search quality configuration
        """
        self.config = config or get_search_quality_config()

    def rerank(
        self,
        results: list[HybridSearchResult],
        query_embedding: Optional[list[float]] = None,
        top_k: int = 5,
    ) -> list[HybridSearchResult]:
        """Rerank results using MMR to maximize diversity.

        Args:
            results: List of search results with embeddings
            query_embedding: Query embedding for relevance calculation
            top_k: Number of results to return

        Returns:
            Reranked list of HybridSearchResult
        """
        if not self.config.enable_mmr:
            return results[:top_k]

        if not results:
            return []

        if len(results) <= top_k:
            # No need to rerank if we have fewer results than needed
            for result in results:
                result.mmr_score = result.combined_score
            return results

        # Check if we have embeddings for MMR
        has_embeddings = all(r.embedding is not None for r in results)

        if not has_embeddings:
            # Fall back to text-based diversity using jaccard similarity
            return self._rerank_text_based(results, top_k)

        # Full MMR with embeddings
        return self._rerank_embedding_based(results, query_embedding, top_k)

    def _rerank_embedding_based(
        self,
        results: list[HybridSearchResult],
        query_embedding: Optional[list[float]],
        top_k: int,
    ) -> list[HybridSearchResult]:
        """Rerank using embedding-based similarity.

        Args:
            results: Search results with embeddings
            query_embedding: Query embedding
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        selected: list[HybridSearchResult] = []
        candidates = list(results)
        lambda_param = self.config.mmr_lambda

        while len(selected) < top_k and candidates:
            best_score = float('-inf')
            best_idx = 0

            for i, candidate in enumerate(candidates):
                # Relevance score (from combined search score)
                relevance = candidate.combined_score

                # Diversity: max similarity to already selected documents
                max_sim_to_selected = 0.0
                if selected and candidate.embedding:
                    for sel in selected:
                        if sel.embedding:
                            sim = self._cosine_similarity(
                                candidate.embedding,
                                sel.embedding
                            )
                            max_sim_to_selected = max(max_sim_to_selected, sim)

                # MMR score
                mmr_score = (
                    lambda_param * relevance -
                    (1 - lambda_param) * max_sim_to_selected
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            # Select best candidate
            best_candidate = candidates.pop(best_idx)
            best_candidate.mmr_score = best_score
            selected.append(best_candidate)

        logger.debug(f"MMR reranking: {len(results)} -> {len(selected)} results")
        return selected

    def _rerank_text_based(
        self,
        results: list[HybridSearchResult],
        top_k: int,
    ) -> list[HybridSearchResult]:
        """Rerank using text-based similarity (Jaccard).

        Fallback when embeddings are not available.

        Args:
            results: Search results
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        selected: list[HybridSearchResult] = []
        candidates = list(results)
        lambda_param = self.config.mmr_lambda

        while len(selected) < top_k and candidates:
            best_score = float('-inf')
            best_idx = 0

            for i, candidate in enumerate(candidates):
                # Relevance score
                relevance = candidate.combined_score

                # Diversity: max text similarity to selected documents
                max_sim_to_selected = 0.0
                if selected:
                    candidate_tokens = self._tokenize(candidate.chunk_text)
                    for sel in selected:
                        sel_tokens = self._tokenize(sel.chunk_text)
                        sim = self._jaccard_similarity(candidate_tokens, sel_tokens)
                        max_sim_to_selected = max(max_sim_to_selected, sim)

                # MMR score
                mmr_score = (
                    lambda_param * relevance -
                    (1 - lambda_param) * max_sim_to_selected
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            best_candidate = candidates.pop(best_idx)
            best_candidate.mmr_score = best_score
            selected.append(best_candidate)

        logger.debug(f"MMR text-based reranking: {len(results)} -> {len(selected)} results")
        return selected

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0-1)
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calculate Jaccard similarity between two sets.

        Args:
            set1: First set of tokens
            set2: Second set of tokens

        Returns:
            Jaccard similarity (0-1)
        """
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def _tokenize(self, text: str) -> set:
        """Tokenize text into a set of words.

        Args:
            text: Input text

        Returns:
            Set of lowercase tokens
        """
        import re
        # Simple tokenization: lowercase words
        words = re.findall(r'\b\w+\b', text.lower())
        return set(words)

    def calculate_diversity_score(
        self,
        results: list[HybridSearchResult]
    ) -> float:
        """Calculate overall diversity score for a set of results.

        Args:
            results: List of search results

        Returns:
            Diversity score (0-1, higher = more diverse)
        """
        if len(results) < 2:
            return 1.0

        # Calculate pairwise similarities
        total_similarity = 0.0
        pair_count = 0

        for i, r1 in enumerate(results):
            for j, r2 in enumerate(results):
                if i < j:
                    if r1.embedding and r2.embedding:
                        sim = self._cosine_similarity(r1.embedding, r2.embedding)
                    else:
                        t1 = self._tokenize(r1.chunk_text)
                        t2 = self._tokenize(r2.chunk_text)
                        sim = self._jaccard_similarity(t1, t2)

                    total_similarity += sim
                    pair_count += 1

        if pair_count == 0:
            return 1.0

        avg_similarity = total_similarity / pair_count
        return 1.0 - avg_similarity  # Invert: lower similarity = higher diversity


# Singleton instance
_reranker: Optional[MMRReranker] = None


def get_mmr_reranker() -> MMRReranker:
    """Get the global MMR reranker instance.

    Returns:
        MMRReranker instance
    """
    global _reranker
    if _reranker is None:
        _reranker = MMRReranker()
    return _reranker


def reset_mmr_reranker():
    """Reset the global MMR reranker instance."""
    global _reranker
    _reranker = None


def rerank_with_mmr(
    results: list[HybridSearchResult],
    query_embedding: Optional[list[float]] = None,
    top_k: int = 5,
) -> list[HybridSearchResult]:
    """Convenience function to rerank results with MMR.

    Args:
        results: Search results to rerank
        query_embedding: Query embedding
        top_k: Number of results

    Returns:
        Reranked results
    """
    reranker = get_mmr_reranker()
    return reranker.rerank(results, query_embedding, top_k)
