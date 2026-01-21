"""
Hybrid retriever for RAG system.

Combines vector similarity search with knowledge graph search
for improved retrieval quality.
"""

import logging
import time
from typing import Optional

from src.rag.models import (
    HybridSearchResult,
    RAGQueryRequest,
    RAGQueryResponse,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retriever combining vector and graph search."""

    def __init__(
        self,
        embedding_manager=None,
        vector_store=None,
        graphiti_client=None,
        vector_weight: float = 0.7,
        graph_weight: float = 0.3,
    ):
        """Initialize hybrid retriever.

        Args:
            embedding_manager: EmbeddingManager instance
            vector_store: NeonVectorStore instance
            graphiti_client: GraphitiClient instance (optional)
            vector_weight: Weight for vector search scores (0-1)
            graph_weight: Weight for graph search scores (0-1)
        """
        self._embedding_manager = embedding_manager
        self._vector_store = vector_store
        self._graphiti_client = graphiti_client
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    def _get_embedding_manager(self):
        """Get or create embedding manager."""
        if self._embedding_manager is None:
            from src.rag.embedding_manager import CachedEmbeddingManager
            self._embedding_manager = CachedEmbeddingManager()
        return self._embedding_manager

    def _get_vector_store(self):
        """Get or create vector store."""
        if self._vector_store is None:
            from src.rag.neon_vector_store import get_vector_store
            self._vector_store = get_vector_store()
        return self._vector_store

    def _get_graphiti_client(self):
        """Get graphiti client if available."""
        if self._graphiti_client is None:
            try:
                from src.rag.graphiti_client import get_graphiti_client
                self._graphiti_client = get_graphiti_client()
            except Exception as e:
                logger.debug(f"Graphiti client not available: {e}")
                return None
        return self._graphiti_client

    def search(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Perform hybrid search.

        Args:
            request: Search request

        Returns:
            RAGQueryResponse with combined results
        """
        start_time = time.time()

        # Generate query embedding
        embedding_manager = self._get_embedding_manager()
        query_embedding = embedding_manager.generate_embedding(request.query)

        # Vector search
        vector_store = self._get_vector_store()
        vector_results = vector_store.search(
            query_embedding=query_embedding,
            top_k=request.top_k * 2,  # Get more for re-ranking
            similarity_threshold=request.similarity_threshold,
        )

        # Graph search (optional)
        graph_results = []
        if request.use_graph_search:
            graphiti = self._get_graphiti_client()
            if graphiti:
                try:
                    graph_results = graphiti.search(
                        request.query,
                        num_results=request.top_k,
                    )
                except Exception as e:
                    logger.warning(f"Graph search failed: {e}")

        # Combine and re-rank results
        combined_results = self._merge_results(
            vector_results,
            graph_results,
            request.top_k,
        )

        # Build context text
        context_text = self._build_context(combined_results)

        processing_time = (time.time() - start_time) * 1000

        return RAGQueryResponse(
            query=request.query,
            results=combined_results,
            total_results=len(combined_results),
            processing_time_ms=processing_time,
            context_text=context_text,
        )

    def search_simple(
        self,
        query: str,
        top_k: int = 5,
        use_graph: bool = True,
        similarity_threshold: float = 0.3,
    ) -> RAGQueryResponse:
        """Simple search interface.

        Args:
            query: Search query text
            top_k: Number of results
            use_graph: Whether to use graph search
            similarity_threshold: Minimum similarity score

        Returns:
            RAGQueryResponse with results
        """
        request = RAGQueryRequest(
            query=query,
            top_k=top_k,
            use_graph_search=use_graph,
            similarity_threshold=similarity_threshold,
        )
        return self.search(request)

    def _merge_results(
        self,
        vector_results: list[VectorSearchResult],
        graph_results: list,
        top_k: int,
    ) -> list[HybridSearchResult]:
        """Merge and re-rank vector and graph results.

        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            top_k: Number of final results

        Returns:
            List of merged HybridSearchResult
        """
        # Create lookup for vector results by document_id + chunk_index
        results_map: dict[str, HybridSearchResult] = {}

        # Process vector results
        for vr in vector_results:
            key = f"{vr.document_id}:{vr.chunk_index}"

            # Get document filename from metadata or use ID
            filename = "Unknown"
            if vr.metadata and "filename" in vr.metadata:
                filename = vr.metadata["filename"]

            results_map[key] = HybridSearchResult(
                chunk_text=vr.chunk_text,
                document_id=vr.document_id,
                document_filename=filename,
                chunk_index=vr.chunk_index,
                vector_score=vr.similarity_score,
                graph_score=0.0,
                combined_score=vr.similarity_score * self.vector_weight,
                related_entities=[],
                metadata=vr.metadata,
            )

        # Process graph results and boost matching chunks
        for gr in graph_results:
            # Try to match graph results to vector results
            # This is a simple approach - could be more sophisticated
            source_doc_id = getattr(gr, "source_document_id", None)
            if source_doc_id:
                # Boost all chunks from this document
                for key, result in results_map.items():
                    if result.document_id == source_doc_id:
                        result.graph_score = max(result.graph_score, getattr(gr, "relevance_score", 0.5))
                        result.related_entities.append(getattr(gr, "entity_name", ""))

            # Also add entities to results that mention similar terms
            entity_name = getattr(gr, "entity_name", "").lower()
            for key, result in results_map.items():
                if entity_name and entity_name in result.chunk_text.lower():
                    result.graph_score = max(result.graph_score, 0.3)
                    if entity_name not in [e.lower() for e in result.related_entities]:
                        result.related_entities.append(getattr(gr, "entity_name", ""))

        # Recalculate combined scores
        for result in results_map.values():
            result.combined_score = (
                result.vector_score * self.vector_weight +
                result.graph_score * self.graph_weight
            )

        # Sort by combined score and return top_k
        sorted_results = sorted(
            results_map.values(),
            key=lambda x: x.combined_score,
            reverse=True,
        )

        return sorted_results[:top_k]

    def _build_context(self, results: list[HybridSearchResult]) -> str:
        """Build context text for LLM from results.

        Args:
            results: Search results

        Returns:
            Formatted context string
        """
        if not results:
            return ""

        context_parts = []

        for i, result in enumerate(results, 1):
            # Format each result as a context chunk
            chunk_header = f"[Source {i}: {result.document_filename}]"
            context_parts.append(chunk_header)
            context_parts.append(result.chunk_text)

            if result.related_entities:
                entities = ", ".join(result.related_entities[:5])
                context_parts.append(f"Related concepts: {entities}")

            context_parts.append("")  # Empty line between chunks

        return "\n".join(context_parts)

    def get_retrieval_stats(self) -> dict:
        """Get retrieval statistics.

        Returns:
            Dict with stats
        """
        stats = {
            "vector_store_available": False,
            "graph_search_available": False,
            "embedding_model": "unknown",
        }

        try:
            vs = self._get_vector_store()
            if vs and vs.health_check():
                stats["vector_store_available"] = True
                vs_stats = vs.get_stats()
                stats.update(vs_stats)
        except Exception:
            pass

        try:
            gc = self._get_graphiti_client()
            if gc:
                stats["graph_search_available"] = True
        except Exception:
            pass

        try:
            em = self._get_embedding_manager()
            if em:
                stats["embedding_model"] = em.model
        except Exception:
            pass

        return stats


# Singleton instance
_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    """Get the global hybrid retriever instance.

    Returns:
        HybridRetriever instance
    """
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def reset_hybrid_retriever():
    """Reset the global hybrid retriever instance."""
    global _retriever
    _retriever = None
