"""
Streaming hybrid retriever for RAG system.

Provides parallel search execution with streaming callbacks
for progressive result display. Supports cancellation.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from rag.models import (
    HybridSearchResult,
    QueryExpansion,
    RAGQueryRequest,
    RAGQueryResponse,
    VectorSearchResult,
)
from rag.search_config import SearchQualityConfig, get_search_quality_config
from rag.streaming_models import (
    CancellationError,
    CancellationToken,
    StreamCallback,
    StreamEvent,
    StreamEventType,
    StreamingSearchRequest,
    StreamingSearchState,
)

logger = logging.getLogger(__name__)


class StreamingHybridRetriever:
    """Hybrid retriever with streaming support and parallel execution.

    Executes vector, BM25, and graph searches in parallel, emitting
    results as they become available for progressive display.
    """

    # Maximum number of concurrent search operations
    MAX_CONCURRENT_SEARCHES = 3

    def __init__(
        self,
        embedding_manager=None,
        vector_store=None,
        graphiti_client=None,
        config: Optional[SearchQualityConfig] = None,
    ):
        """Initialize streaming hybrid retriever.

        Args:
            embedding_manager: EmbeddingManager instance
            vector_store: NeonVectorStore instance
            graphiti_client: GraphitiClient instance (optional)
            config: Search quality configuration
        """
        self._embedding_manager = embedding_manager
        self._vector_store = vector_store
        self._graphiti_client = graphiti_client

        # Load config
        self.config = config or get_search_quality_config()

        # Lazy-loaded helpers
        self._query_expander = None
        self._adaptive_threshold = None
        self._mmr_reranker = None
        self._bm25_searcher = None

        # Thread pool for parallel searches
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_SEARCHES,
            thread_name_prefix="rag_search_"
        )

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

    def search_streaming(
        self,
        request: StreamingSearchRequest,
        callback: StreamCallback,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> RAGQueryResponse:
        """Perform streaming hybrid search with parallel execution.

        Executes vector, BM25, and graph searches in parallel,
        emitting results via callback as they become available.

        Args:
            request: Streaming search request
            callback: Callback function for stream events
            cancellation_token: Optional token for cancellation

        Returns:
            RAGQueryResponse with combined results

        Raises:
            CancellationError: If operation was cancelled
        """
        token = cancellation_token or CancellationToken()
        state = StreamingSearchState(
            request=request,
            cancellation_token=token,
        )

        try:
            # Emit search started event
            callback(StreamEvent(
                event_type=StreamEventType.SEARCH_STARTED,
                progress_percent=0.0,
                message="Starting document search...",
            ))

            # Check for cancellation
            token.raise_if_cancelled()

            # Step 1: Query expansion (if enabled)
            if request.enable_query_expansion and self.config.enable_query_expansion:
                expander = self._get_query_expander()
                if expander:
                    state.query_expansion = expander.expand_query(request.query)
                    logger.debug(f"Query expansion: {len(state.query_expansion.expanded_terms)} terms")

            # Check for cancellation
            token.raise_if_cancelled()

            # Step 2: Generate query embedding
            callback(StreamEvent(
                event_type=StreamEventType.PROGRESS,
                progress_percent=10.0,
                message="Generating query embedding...",
            ))

            embedding_manager = self._get_embedding_manager()
            state.query_embedding = embedding_manager.generate_embedding(request.query)

            # Check for cancellation
            token.raise_if_cancelled()

            # Step 3: Execute searches in parallel
            callback(StreamEvent(
                event_type=StreamEventType.PROGRESS,
                progress_percent=20.0,
                message="Searching documents...",
            ))

            self._execute_parallel_searches(state, callback)

            # Check for cancellation
            token.raise_if_cancelled()

            # Step 4: Merge and score results
            callback(StreamEvent(
                event_type=StreamEventType.PROGRESS,
                progress_percent=80.0,
                message="Ranking results...",
            ))

            self._merge_and_rank_results(state, callback)

            # Step 5: Apply MMR reranking if enabled
            if request.enable_mmr and self.config.enable_mmr:
                self._apply_mmr(state, callback)

            # Step 6: Build final response
            token.raise_if_cancelled()

            context_text = self._build_context(state.merged_results)

            # Emit search complete event
            callback(StreamEvent(
                event_type=StreamEventType.SEARCH_COMPLETE,
                progress_percent=100.0,
                data={
                    "total_results": len(state.merged_results),
                    "processing_time_ms": state.elapsed_ms,
                },
                message=f"Found {len(state.merged_results)} results in {state.elapsed_ms:.0f}ms",
            ))

            # Determine what features were used
            bm25_enabled = len(state.bm25_results) > 0
            mmr_applied = request.enable_mmr and self.config.enable_mmr

            return RAGQueryResponse(
                query=request.query,
                results=state.merged_results,
                total_results=len(state.merged_results),
                processing_time_ms=state.elapsed_ms,
                context_text=context_text,
                query_expansion=state.query_expansion,
                adaptive_threshold_used=request.similarity_threshold,
                bm25_enabled=bm25_enabled,
                mmr_applied=mmr_applied,
            )

        except CancellationError as e:
            callback(StreamEvent(
                event_type=StreamEventType.CANCELLED,
                message=str(e),
            ))
            raise

        except Exception as e:
            logger.error(f"Streaming search error: {e}")
            state.error = e
            callback(StreamEvent(
                event_type=StreamEventType.ERROR,
                data=str(e),
                message=f"Search error: {str(e)}",
            ))
            raise

    def _execute_parallel_searches(
        self,
        state: StreamingSearchState,
        callback: StreamCallback,
    ) -> None:
        """Execute vector, BM25, and graph searches in parallel.

        Results are emitted via callback as they complete.

        Args:
            state: Current search state
            callback: Event callback
        """
        request = state.request
        token = state.cancellation_token
        fetch_k = request.top_k * 3  # Get extra for filtering

        # Expanded terms for BM25
        expanded_terms = []
        if state.query_expansion:
            expanded_terms = state.query_expansion.expanded_terms

        # Define search tasks
        futures = {}

        # Submit vector search
        def vector_search():
            token.raise_if_cancelled()
            vector_store = self._get_vector_store()
            return vector_store.search(
                query_embedding=state.query_embedding,
                top_k=fetch_k,
                similarity_threshold=0.0,
                ef_search=request.ef_search,
            )

        futures[self._executor.submit(vector_search)] = "vector"

        # Submit BM25 search (if enabled)
        if request.enable_bm25 and self.config.enable_bm25:
            def bm25_search():
                token.raise_if_cancelled()
                bm25_searcher = self._get_bm25_searcher()
                if bm25_searcher:
                    return bm25_searcher.search(
                        request.query,
                        expanded_terms=expanded_terms,
                        top_k=fetch_k,
                    )
                return []

            futures[self._executor.submit(bm25_search)] = "bm25"

        # Submit graph search (if enabled)
        if request.use_graph_search:
            def graph_search():
                token.raise_if_cancelled()
                graphiti = self._get_graphiti_client()
                if graphiti:
                    return graphiti.search(
                        request.query,
                        num_results=request.top_k,
                    )
                return []

            futures[self._executor.submit(graph_search)] = "graph"

        # Process results as they complete
        completed_count = 0
        total_searches = len(futures)

        for future in as_completed(futures):
            search_type = futures[future]

            try:
                token.raise_if_cancelled()
                results = future.result()

                # Store results and emit event
                if search_type == "vector":
                    state.vector_results = results
                    callback(StreamEvent(
                        event_type=StreamEventType.VECTOR_RESULTS,
                        data=results,
                        progress_percent=20 + (completed_count + 1) * 20,
                        message=f"Vector search: {len(results)} results",
                    ))

                elif search_type == "bm25":
                    state.bm25_results = results
                    callback(StreamEvent(
                        event_type=StreamEventType.BM25_RESULTS,
                        data=results,
                        progress_percent=20 + (completed_count + 1) * 20,
                        message=f"BM25 search: {len(results)} results",
                    ))

                elif search_type == "graph":
                    state.graph_results = results
                    callback(StreamEvent(
                        event_type=StreamEventType.GRAPH_RESULTS,
                        data=results,
                        progress_percent=20 + (completed_count + 1) * 20,
                        message=f"Graph search: {len(results)} results",
                    ))

                completed_count += 1

            except CancellationError:
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                raise

            except Exception as e:
                logger.warning(f"{search_type} search failed: {e}")
                # Continue with other searches

    def _merge_and_rank_results(
        self,
        state: StreamingSearchState,
        callback: StreamCallback,
    ) -> None:
        """Merge and rank results from all search sources.

        Args:
            state: Current search state
            callback: Event callback
        """
        request = state.request

        # Calculate adaptive threshold if enabled
        threshold = request.similarity_threshold
        if request.enable_adaptive_threshold and self.config.enable_adaptive_threshold:
            threshold_calc = self._get_adaptive_threshold()
            if threshold_calc:
                scores = [r.similarity_score for r in state.vector_results]
                query_word_count = len(request.query.split())
                threshold = threshold_calc.calculate_threshold(
                    scores,
                    query_word_count,
                    request.similarity_threshold,
                )
                logger.debug(f"Adaptive threshold: {threshold:.3f}")

        # Merge results
        results_map: dict[str, HybridSearchResult] = {}

        # Process vector results
        for vr in state.vector_results:
            if vr.similarity_score < threshold:
                continue

            key = f"{vr.document_id}:{vr.chunk_index}"
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
                embedding=None,
            )

        # Process BM25 results
        for br in state.bm25_results:
            key = f"{br.document_id}:{br.chunk_index}"

            if key in results_map:
                results_map[key].bm25_score = br.bm25_score
            else:
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

        # Process graph results
        for gr in state.graph_results:
            source_doc_id = getattr(gr, "source_document_id", None)
            relevance = getattr(gr, "relevance_score", 0.5)
            entity_name = getattr(gr, "entity_name", "")

            if source_doc_id:
                for key, result in results_map.items():
                    if result.document_id == source_doc_id:
                        result.graph_score = max(result.graph_score, relevance)
                        if entity_name and entity_name not in result.related_entities:
                            result.related_entities.append(entity_name)

            entity_lower = entity_name.lower() if entity_name else ""
            for key, result in results_map.items():
                if entity_lower and entity_lower in result.chunk_text.lower():
                    result.graph_score = max(result.graph_score, 0.3)
                    if entity_name and entity_name not in result.related_entities:
                        result.related_entities.append(entity_name)

        # Calculate combined scores
        for result in results_map.values():
            result.combined_score = (
                result.vector_score * self.config.vector_weight +
                result.bm25_score * self.config.bm25_weight +
                result.graph_score * self.config.graph_weight
            )

        # Sort by combined score
        sorted_results = sorted(
            results_map.values(),
            key=lambda x: x.combined_score,
            reverse=True,
        )

        # Limit to fetch_k before MMR
        state.merged_results = sorted_results[:request.top_k * 3]

    def _apply_mmr(
        self,
        state: StreamingSearchState,
        callback: StreamCallback,
    ) -> None:
        """Apply MMR diversity reranking.

        Args:
            state: Current search state
            callback: Event callback
        """
        request = state.request

        if len(state.merged_results) <= request.top_k:
            return

        mmr_reranker = self._get_mmr_reranker()
        if mmr_reranker:
            callback(StreamEvent(
                event_type=StreamEventType.PROGRESS,
                progress_percent=90.0,
                message="Applying diversity reranking...",
            ))

            state.merged_results = mmr_reranker.rerank(
                state.merged_results,
                state.query_embedding,
                request.top_k,
            )
            logger.debug(f"MMR reranking applied, {len(state.merged_results)} results")
        else:
            # Just take top_k
            state.merged_results = state.merged_results[:request.top_k]

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
            chunk_header = f"[Source {i}: {result.document_filename}]"
            context_parts.append(chunk_header)
            context_parts.append(result.chunk_text)

            if result.related_entities:
                entities = ", ".join(result.related_entities[:5])
                context_parts.append(f"Related concepts: {entities}")

            context_parts.append("")

        return "\n".join(context_parts)

    def search(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Non-streaming search (delegates to streaming with no-op callback).

        Args:
            request: Search request

        Returns:
            RAGQueryResponse with results
        """
        streaming_request = StreamingSearchRequest(
            query=request.query,
            top_k=request.top_k,
            use_graph_search=request.use_graph_search,
            similarity_threshold=request.similarity_threshold,
            enable_query_expansion=request.enable_query_expansion,
            enable_adaptive_threshold=request.enable_adaptive_threshold,
            enable_bm25=request.enable_bm25,
            enable_mmr=request.enable_mmr,
        )

        def noop_callback(event: StreamEvent):
            pass

        return self.search_streaming(streaming_request, noop_callback)

    def close(self):
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=False)


# Singleton instance
_streaming_retriever: Optional[StreamingHybridRetriever] = None


def get_streaming_retriever() -> StreamingHybridRetriever:
    """Get the global streaming hybrid retriever instance.

    Returns:
        StreamingHybridRetriever instance
    """
    global _streaming_retriever
    if _streaming_retriever is None:
        _streaming_retriever = StreamingHybridRetriever()
    return _streaming_retriever


def reset_streaming_retriever():
    """Reset the global streaming hybrid retriever instance."""
    global _streaming_retriever
    if _streaming_retriever:
        _streaming_retriever.close()
        _streaming_retriever = None
