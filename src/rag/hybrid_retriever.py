"""
Hybrid retriever for RAG system.

Combines vector similarity search with knowledge graph search
for improved retrieval quality.

Enhanced with:
- Adaptive similarity threshold
- Medical query expansion
- BM25 hybrid search
- MMR result diversity
"""

import logging
import time
from typing import Optional

from rag.models import (
    HybridSearchResult,
    QueryExpansion,
    RAGQueryRequest,
    RAGQueryResponse,
    VectorSearchResult,
)
from rag.search_config import SearchQualityConfig, get_search_quality_config

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retriever combining vector and graph search."""

    def __init__(
        self,
        embedding_manager=None,
        vector_store=None,
        graphiti_client=None,
        vector_weight: float = 0.5,
        graph_weight: float = 0.2,
        bm25_weight: float = 0.3,
        config: Optional[SearchQualityConfig] = None,
    ):
        """Initialize hybrid retriever.

        Args:
            embedding_manager: EmbeddingManager instance
            vector_store: NeonVectorStore instance
            graphiti_client: GraphitiClient instance (optional)
            vector_weight: Weight for vector search scores (0-1)
            graph_weight: Weight for graph search scores (0-1)
            bm25_weight: Weight for BM25 keyword search scores (0-1)
            config: Search quality configuration
        """
        self._embedding_manager = embedding_manager
        self._vector_store = vector_store
        self._graphiti_client = graphiti_client
        self._query_expander = None
        self._adaptive_threshold = None
        self._mmr_reranker = None
        self._bm25_searcher = None

        # Load config
        self.config = config or get_search_quality_config()

        # Use config weights if not explicitly provided
        self.vector_weight = self.config.vector_weight if config else vector_weight
        self.graph_weight = self.config.graph_weight if config else graph_weight
        self.bm25_weight = self.config.bm25_weight if config else bm25_weight

    def _get_embedding_manager(self):
        """Get or create embedding manager."""
        if self._embedding_manager is None:
            from rag.embedding_manager import CachedEmbeddingManager
            self._embedding_manager = CachedEmbeddingManager()
        return self._embedding_manager

    def _get_vector_store(self):
        """Get or create vector store."""
        if self._vector_store is None:
            from rag.neon_vector_store import get_vector_store
            self._vector_store = get_vector_store()
        return self._vector_store

    def _get_graphiti_client(self):
        """Get graphiti client if available."""
        if self._graphiti_client is None:
            try:
                from rag.graphiti_client import get_graphiti_client
                self._graphiti_client = get_graphiti_client()
            except Exception as e:
                logger.debug(f"Graphiti client not available: {e}")
                return None
        return self._graphiti_client

    def _get_query_expander(self):
        """Get or create query expander."""
        if self._query_expander is None:
            try:
                from rag.query_expander import MedicalQueryExpander
                self._query_expander = MedicalQueryExpander(self.config)
            except Exception as e:
                logger.debug(f"Query expander not available: {e}")
                return None
        return self._query_expander

    def _get_adaptive_threshold(self):
        """Get or create adaptive threshold calculator."""
        if self._adaptive_threshold is None:
            try:
                from rag.adaptive_threshold import AdaptiveThresholdCalculator
                self._adaptive_threshold = AdaptiveThresholdCalculator(self.config)
            except Exception as e:
                logger.debug(f"Adaptive threshold not available: {e}")
                return None
        return self._adaptive_threshold

    def _get_mmr_reranker(self):
        """Get or create MMR reranker."""
        if self._mmr_reranker is None:
            try:
                from rag.mmr_reranker import MMRReranker
                self._mmr_reranker = MMRReranker(self.config)
            except Exception as e:
                logger.debug(f"MMR reranker not available: {e}")
                return None
        return self._mmr_reranker

    def _get_bm25_searcher(self):
        """Get or create BM25 searcher."""
        if self._bm25_searcher is None:
            try:
                from rag.bm25_search import BM25Searcher
                self._bm25_searcher = BM25Searcher(
                    self._get_vector_store(),
                    self.config
                )
            except Exception as e:
                logger.debug(f"BM25 searcher not available: {e}")
                return None
        return self._bm25_searcher

    def search(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Perform hybrid search with search quality improvements.

        Args:
            request: Search request

        Returns:
            RAGQueryResponse with combined results
        """
        start_time = time.time()

        # Track search quality features used
        query_expansion: Optional[QueryExpansion] = None
        adaptive_threshold_used: Optional[float] = None
        bm25_enabled = False
        mmr_applied = False

        # Step 1: Query expansion (if enabled)
        expanded_terms = []
        if request.enable_query_expansion and self.config.enable_query_expansion:
            expander = self._get_query_expander()
            if expander:
                query_expansion = expander.expand_query(request.query)
                expanded_terms = query_expansion.expanded_terms
                logger.debug(f"Query expansion: {len(expanded_terms)} terms added")

        # Step 2: Generate query embedding
        embedding_manager = self._get_embedding_manager()
        query_embedding = embedding_manager.generate_embedding(request.query)

        # Step 3: Vector search (get more for re-ranking)
        vector_store = self._get_vector_store()
        fetch_k = request.top_k * 3  # Get extra for filtering and diversity
        vector_results = vector_store.search(
            query_embedding=query_embedding,
            top_k=fetch_k,
            similarity_threshold=0.0,  # Low threshold, will filter later
        )

        # Step 4: BM25 search (if enabled)
        bm25_results = []
        if request.enable_bm25 and self.config.enable_bm25:
            bm25_searcher = self._get_bm25_searcher()
            if bm25_searcher:
                try:
                    bm25_results = bm25_searcher.search(
                        request.query,
                        expanded_terms=expanded_terms,
                        top_k=fetch_k,
                    )
                    bm25_enabled = True
                    logger.debug(f"BM25 search: {len(bm25_results)} results")
                except Exception as e:
                    logger.warning(f"BM25 search failed: {e}")

        # Step 5: Graph search (optional)
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

        # Step 6: Adaptive threshold (if enabled)
        if request.enable_adaptive_threshold and self.config.enable_adaptive_threshold:
            threshold_calc = self._get_adaptive_threshold()
            if threshold_calc:
                scores = [r.similarity_score for r in vector_results]
                query_word_count = len(request.query.split())
                adaptive_threshold_used = threshold_calc.calculate_threshold(
                    scores,
                    query_word_count,
                    request.similarity_threshold,
                )
                logger.debug(f"Adaptive threshold: {adaptive_threshold_used:.3f}")
        else:
            adaptive_threshold_used = request.similarity_threshold

        # Step 7: Merge and score results
        combined_results = self._merge_results_enhanced(
            vector_results,
            bm25_results,
            graph_results,
            query_embedding,
            adaptive_threshold_used or request.similarity_threshold,
            fetch_k,
        )

        # Step 8: MMR reranking (if enabled)
        if request.enable_mmr and self.config.enable_mmr and len(combined_results) > request.top_k:
            mmr_reranker = self._get_mmr_reranker()
            if mmr_reranker:
                combined_results = mmr_reranker.rerank(
                    combined_results,
                    query_embedding,
                    request.top_k,
                )
                mmr_applied = True
                logger.debug(f"MMR reranking applied, {len(combined_results)} results")
        else:
            # Just take top_k
            combined_results = combined_results[:request.top_k]

        # Build context text
        context_text = self._build_context(combined_results)

        processing_time = (time.time() - start_time) * 1000

        return RAGQueryResponse(
            query=request.query,
            results=combined_results,
            total_results=len(combined_results),
            processing_time_ms=processing_time,
            context_text=context_text,
            query_expansion=query_expansion,
            adaptive_threshold_used=adaptive_threshold_used,
            bm25_enabled=bm25_enabled,
            mmr_applied=mmr_applied,
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
        """Merge and re-rank vector and graph results (legacy method).

        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            top_k: Number of final results

        Returns:
            List of merged HybridSearchResult
        """
        # Delegate to enhanced method with empty BM25 results
        return self._merge_results_enhanced(
            vector_results,
            [],  # No BM25 results
            graph_results,
            None,  # No query embedding
            0.0,  # No threshold filtering
            top_k,
        )

    def _merge_results_enhanced(
        self,
        vector_results: list[VectorSearchResult],
        bm25_results: list,
        graph_results: list,
        query_embedding: Optional[list[float]],
        similarity_threshold: float,
        top_k: int,
    ) -> list[HybridSearchResult]:
        """Merge and score results from vector, BM25, and graph search.

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            graph_results: Results from graph search
            query_embedding: Query embedding for storing in results
            similarity_threshold: Minimum similarity to include
            top_k: Maximum results before MMR

        Returns:
            List of merged HybridSearchResult
        """
        # Create lookup for results by document_id + chunk_index
        results_map: dict[str, HybridSearchResult] = {}

        # Process vector results
        for vr in vector_results:
            # Skip if below threshold
            if vr.similarity_score < similarity_threshold:
                continue

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
                bm25_score=0.0,
                combined_score=0.0,
                mmr_score=0.0,
                related_entities=[],
                metadata=vr.metadata,
                embedding=None,  # Will be set if needed for MMR
            )

        # Process BM25 results
        for br in bm25_results:
            key = f"{br.document_id}:{br.chunk_index}"

            if key in results_map:
                # Update existing result with BM25 score
                results_map[key].bm25_score = br.bm25_score
            else:
                # Add new result from BM25
                filename = "Unknown"
                if br.metadata and "filename" in br.metadata:
                    filename = br.metadata["filename"]

                results_map[key] = HybridSearchResult(
                    chunk_text=br.chunk_text,
                    document_id=br.document_id,
                    document_filename=filename,
                    chunk_index=br.chunk_index,
                    vector_score=0.0,
                    graph_score=0.0,
                    bm25_score=br.bm25_score,
                    combined_score=0.0,
                    mmr_score=0.0,
                    related_entities=[],
                    metadata=br.metadata,
                    embedding=None,
                )

        # Process graph results and boost matching chunks
        for gr in graph_results:
            source_doc_id = getattr(gr, "source_document_id", None)
            relevance = getattr(gr, "relevance_score", 0.5)
            entity_name = getattr(gr, "entity_name", "")

            if source_doc_id:
                # Boost all chunks from this document
                for key, result in results_map.items():
                    if result.document_id == source_doc_id:
                        result.graph_score = max(result.graph_score, relevance)
                        if entity_name and entity_name not in result.related_entities:
                            result.related_entities.append(entity_name)

            # Also boost results that mention the entity
            entity_lower = entity_name.lower() if entity_name else ""
            for key, result in results_map.items():
                if entity_lower and entity_lower in result.chunk_text.lower():
                    result.graph_score = max(result.graph_score, 0.3)
                    if entity_name and entity_name not in result.related_entities:
                        result.related_entities.append(entity_name)

        # Calculate combined scores
        for result in results_map.values():
            result.combined_score = (
                result.vector_score * self.vector_weight +
                result.bm25_score * self.bm25_weight +
                result.graph_score * self.graph_weight
            )

        # Sort by combined score
        sorted_results = sorted(
            results_map.values(),
            key=lambda x: x.combined_score,
            reverse=True,
        )

        # Limit to top_k before MMR (MMR will further reduce)
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
