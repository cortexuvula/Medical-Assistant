"""
Clinical Guidelines Retriever

Retrieves relevant clinical guidelines for compliance checking.
Combines vector search and knowledge graph search from the SEPARATE
guidelines database (not the main patient RAG system).

Architecture Note:
    This retriever ONLY queries the guidelines database.
    It has NO access to patient documents or the main RAG system.
    This is intentional for data isolation and security.
"""

import logging
import time
from typing import Any, Optional

from src.rag.guidelines_models import (
    GuidelineSearchResult,
    GuidelineSearchQuery,
)
from src.rag.guidelines_vector_store import get_guidelines_vector_store
from src.rag.guidelines_graphiti_client import get_guidelines_graphiti_client


logger = logging.getLogger(__name__)


class GuidelinesRetriever:
    """Retrieves relevant clinical guidelines for compliance checking.

    Combines:
    - Vector similarity search for semantic matching
    - BM25 keyword search for exact term matching
    - Knowledge graph search for relationship-based retrieval

    All searches are performed against the SEPARATE guidelines database.
    """

    def __init__(
        self,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.3,
        graph_weight: float = 0.2,
        enable_bm25: bool = True,
        enable_graph: bool = True,
    ):
        """Initialize the guidelines retriever.

        Args:
            vector_weight: Weight for vector search results (0-1)
            bm25_weight: Weight for BM25 search results (0-1)
            graph_weight: Weight for knowledge graph results (0-1)
            enable_bm25: Whether to enable BM25 keyword search
            enable_graph: Whether to enable knowledge graph search
        """
        self._vector_weight = vector_weight
        self._bm25_weight = bm25_weight
        self._graph_weight = graph_weight
        self._enable_bm25 = enable_bm25
        self._enable_graph = enable_graph
        self._embedding_model = "text-embedding-3-small"

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for query text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            from openai import OpenAI
            import os

            # Get API key
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                from src.managers.api_key_manager import get_api_key_manager
                manager = get_api_key_manager()
                api_key = manager.get_key("openai")

            if not api_key:
                raise ValueError("OpenAI API key not found")

            client = OpenAI(api_key=api_key)
            response = client.embeddings.create(
                model=self._embedding_model,
                input=text,
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 10,
        specialties: Optional[list[str]] = None,
        sources: Optional[list[str]] = None,
        recommendation_class: Optional[str] = None,
        evidence_level: Optional[str] = None,
        similarity_threshold: float = 0.5,
    ) -> list[GuidelineSearchResult]:
        """Search for relevant clinical guidelines.

        Performs hybrid search combining vector, BM25, and graph results.

        Args:
            query: Search query text
            top_k: Number of results to return
            specialties: Filter by specialties (e.g., ["cardiology", "endocrinology"])
            sources: Filter by sources (e.g., ["AHA", "ADA"])
            recommendation_class: Filter by recommendation class (I, IIa, IIb, III)
            evidence_level: Filter by evidence level (A, B, C)
            similarity_threshold: Minimum similarity score

        Returns:
            List of GuidelineSearchResult objects, sorted by combined score
        """
        start_time = time.time()

        # Get embedding for query
        try:
            query_embedding = self._get_embedding(query)
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            return []

        results_map: dict[str, GuidelineSearchResult] = {}

        # Step 1: Vector search
        try:
            vector_store = get_guidelines_vector_store()
            vector_results = vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k * 2,  # Get more for merging
                similarity_threshold=similarity_threshold,
                filter_specialties=specialties,
                filter_sources=sources,
                filter_recommendation_class=recommendation_class,
                filter_evidence_level=evidence_level,
            )

            for result in vector_results:
                key = f"{result.guideline_id}_{result.chunk_index}"
                if key not in results_map:
                    results_map[key] = result
                # Weight the vector score
                results_map[key].similarity_score = (
                    result.similarity_score * self._vector_weight
                )

        except Exception as e:
            logger.error(f"Vector search failed: {e}")

        # Step 2: BM25 keyword search
        if self._enable_bm25 and self._bm25_weight > 0:
            try:
                vector_store = get_guidelines_vector_store()
                bm25_results = vector_store.search_bm25(
                    query=query,
                    top_k=top_k * 2,
                    filter_specialties=specialties,
                    filter_sources=sources,
                )

                for result in bm25_results:
                    key = f"{result.guideline_id}_{result.chunk_index}"
                    if key in results_map:
                        # Add BM25 score to existing result
                        results_map[key].similarity_score += (
                            result.similarity_score * self._bm25_weight
                        )
                    else:
                        # New result from BM25
                        result.similarity_score *= self._bm25_weight
                        results_map[key] = result

            except Exception as e:
                logger.debug(f"BM25 search failed or not available: {e}")

        # Step 3: Knowledge graph search
        if self._enable_graph and self._graph_weight > 0:
            try:
                graphiti = get_guidelines_graphiti_client()
                if graphiti:
                    graph_results = graphiti.search(query, num_results=top_k)

                    for graph_result in graph_results:
                        guideline_id = graph_result.get("guideline_id")
                        if not guideline_id:
                            continue

                        # Find matching vector result to boost
                        for key, result in results_map.items():
                            if result.guideline_id == guideline_id:
                                # Boost score for graph-matched results
                                result.similarity_score += (
                                    graph_result.get("relevance_score", 0.8) * self._graph_weight
                                )
                                # Add related facts to metadata
                                if result.metadata is None:
                                    result.metadata = {}
                                result.metadata["graph_fact"] = graph_result.get("fact", "")
                                break

            except Exception as e:
                logger.debug(f"Graph search failed or not available: {e}")

        # Sort by combined score and limit results
        sorted_results = sorted(
            results_map.values(),
            key=lambda x: x.similarity_score,
            reverse=True,
        )[:top_k]

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Guidelines search completed in {elapsed_ms:.1f}ms, "
            f"found {len(sorted_results)} results"
        )

        return sorted_results

    def search_for_conditions(
        self,
        conditions: list[str],
        top_k: int = 5,
    ) -> list[GuidelineSearchResult]:
        """Search for guidelines related to specific conditions.

        Args:
            conditions: List of medical conditions to search for
            top_k: Number of results per condition

        Returns:
            Deduplicated list of GuidelineSearchResult objects
        """
        results_map: dict[str, GuidelineSearchResult] = {}

        for condition in conditions:
            condition_results = self.search(
                query=f"clinical guidelines for {condition} management treatment",
                top_k=top_k,
            )

            for result in condition_results:
                key = f"{result.guideline_id}_{result.chunk_index}"
                if key not in results_map:
                    results_map[key] = result
                else:
                    # Boost score if matched multiple conditions
                    results_map[key].similarity_score = max(
                        results_map[key].similarity_score,
                        result.similarity_score * 1.1,  # 10% boost
                    )

        return sorted(
            results_map.values(),
            key=lambda x: x.similarity_score,
            reverse=True,
        )

    def search_for_medications(
        self,
        medications: list[str],
        top_k: int = 5,
    ) -> list[GuidelineSearchResult]:
        """Search for guidelines related to specific medications.

        Args:
            medications: List of medications to search for
            top_k: Number of results per medication

        Returns:
            Deduplicated list of GuidelineSearchResult objects
        """
        results_map: dict[str, GuidelineSearchResult] = {}

        for medication in medications:
            med_results = self.search(
                query=f"guideline recommendations for {medication} indication dosing",
                top_k=top_k,
            )

            for result in med_results:
                key = f"{result.guideline_id}_{result.chunk_index}"
                if key not in results_map:
                    results_map[key] = result
                else:
                    results_map[key].similarity_score = max(
                        results_map[key].similarity_score,
                        result.similarity_score * 1.1,
                    )

        return sorted(
            results_map.values(),
            key=lambda x: x.similarity_score,
            reverse=True,
        )

    def get_guideline_context(
        self,
        soap_note: str,
        max_guidelines: int = 10,
    ) -> str:
        """Get formatted guideline context for LLM compliance analysis.

        Args:
            soap_note: The SOAP note to find relevant guidelines for
            max_guidelines: Maximum number of guidelines to include

        Returns:
            Formatted string with relevant guideline excerpts
        """
        # Search for guidelines relevant to the SOAP note
        results = self.search(
            query=soap_note[:2000],  # Limit query length
            top_k=max_guidelines,
            similarity_threshold=0.4,
        )

        if not results:
            return "No relevant clinical guidelines found."

        # Format guidelines for LLM context
        context_parts = ["# Relevant Clinical Guidelines\n"]

        for i, result in enumerate(results, 1):
            parts = [f"\n## Guideline {i}"]

            if result.guideline_title:
                parts.append(f"**Title:** {result.guideline_title}")
            if result.guideline_source:
                parts.append(f"**Source:** {result.guideline_source}")
            if result.guideline_version:
                parts.append(f"**Version:** {result.guideline_version}")
            if result.specialty:
                parts.append(f"**Specialty:** {result.specialty}")
            if result.recommendation_class:
                parts.append(f"**Recommendation Class:** {result.recommendation_class}")
            if result.evidence_level:
                parts.append(f"**Evidence Level:** {result.evidence_level}")

            parts.append(f"\n**Guideline Text:**\n{result.chunk_text}")

            context_parts.append("\n".join(parts))

        return "\n\n".join(context_parts)

    def health_check(self) -> dict:
        """Check the health of the guidelines retrieval system.

        Returns:
            Dict with health status for each component
        """
        health = {
            "vector_store": False,
            "bm25_available": False,
            "graph_store": False,
            "embedding_service": False,
        }

        # Check vector store
        try:
            vector_store = get_guidelines_vector_store()
            health["vector_store"] = vector_store.health_check()
        except Exception as e:
            logger.debug(f"Vector store health check failed: {e}")

        # Check BM25 availability
        if health["vector_store"]:
            try:
                vector_store = get_guidelines_vector_store()
                # Try a simple BM25 search
                results = vector_store.search_bm25("test", top_k=1)
                health["bm25_available"] = True
            except Exception:
                pass

        # Check graph store
        try:
            graphiti = get_guidelines_graphiti_client()
            if graphiti:
                health["graph_store"] = graphiti.health_check()
        except Exception as e:
            logger.debug(f"Graph store health check failed: {e}")

        # Check embedding service
        try:
            self._get_embedding("test")
            health["embedding_service"] = True
        except Exception as e:
            logger.debug(f"Embedding service health check failed: {e}")

        return health


# Singleton instance
_guidelines_retriever: Optional[GuidelinesRetriever] = None


def get_guidelines_retriever() -> GuidelinesRetriever:
    """Get the global guidelines retriever instance."""
    global _guidelines_retriever
    if _guidelines_retriever is None:
        _guidelines_retriever = GuidelinesRetriever()
    return _guidelines_retriever


def reset_guidelines_retriever():
    """Reset the global guidelines retriever instance."""
    global _guidelines_retriever
    _guidelines_retriever = None
