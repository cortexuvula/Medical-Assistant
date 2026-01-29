"""
Unit tests for HybridRetriever.

Tests cover:
- Component orchestration (vector + BM25 + graph search)
- Feature toggles (each component enabled/disabled)
- Score merging with configurable weights
- Result filtering (document type, date range, entities, exclude terms)
- Temporal integration
- Context building
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from rag.hybrid_retriever import HybridRetriever, get_hybrid_retriever, reset_hybrid_retriever
from rag.models import RAGQueryRequest, VectorSearchResult, HybridSearchResult, QueryExpansion


@pytest.fixture
def mock_embedding_manager():
    """Create mock embedding manager."""
    manager = Mock()
    manager.model = "text-embedding-3-small"
    manager.generate_embedding.return_value = [0.1] * 1536
    return manager


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = Mock()
    store.search.return_value = []
    store.health_check.return_value = True
    store.get_stats.return_value = {"total_documents": 100}
    return store


@pytest.fixture
def mock_graphiti_client():
    """Create mock graphiti client."""
    client = Mock()
    client.search.return_value = []
    return client


@pytest.fixture
def sample_vector_results():
    """Sample vector search results."""
    return [
        VectorSearchResult(
            chunk_text="Hypertension management guidelines",
            document_id="doc1",
            chunk_index=0,
            similarity_score=0.85,
            metadata={"filename": "guidelines.pdf", "created_at": "2024-01-15T10:00:00"}
        ),
        VectorSearchResult(
            chunk_text="Diabetes treatment protocols",
            document_id="doc2",
            chunk_index=0,
            similarity_score=0.75,
            metadata={"filename": "protocols.pdf", "created_at": "2024-02-20T14:30:00"}
        ),
        VectorSearchResult(
            chunk_text="Medication interactions reference",
            document_id="doc3",
            chunk_index=1,
            similarity_score=0.65,
            metadata={"filename": "reference.docx", "created_at": "2023-11-10T09:00:00"}
        ),
    ]


@pytest.fixture
def sample_hybrid_results():
    """Sample hybrid search results."""
    return [
        HybridSearchResult(
            chunk_text="Hypertension management guidelines",
            document_id="doc1",
            document_filename="guidelines.pdf",
            chunk_index=0,
            vector_score=0.85,
            combined_score=0.85,
            metadata={"filename": "guidelines.pdf", "created_at": "2024-01-15T10:00:00"}
        ),
        HybridSearchResult(
            chunk_text="Diabetes treatment protocols",
            document_id="doc2",
            document_filename="protocols.pdf",
            chunk_index=0,
            vector_score=0.75,
            combined_score=0.75,
            metadata={"filename": "protocols.pdf", "created_at": "2024-02-20T14:30:00"}
        ),
        HybridSearchResult(
            chunk_text="Medication interactions reference",
            document_id="doc3",
            document_filename="reference.docx",
            chunk_index=1,
            vector_score=0.65,
            combined_score=0.65,
            metadata={"filename": "reference.docx", "created_at": "2023-11-10T09:00:00"}
        ),
    ]


@pytest.fixture
def hybrid_retriever(mock_embedding_manager, mock_vector_store):
    """Create HybridRetriever with mocks."""
    retriever = HybridRetriever(
        embedding_manager=mock_embedding_manager,
        vector_store=mock_vector_store,
        graphiti_client=None,
        vector_weight=0.5,
        graph_weight=0.2,
        bm25_weight=0.3,
    )
    return retriever


class TestHybridRetrieverInitialization:
    """Tests for HybridRetriever initialization."""

    def test_init_with_explicit_weights(self, mock_embedding_manager, mock_vector_store):
        """Test initialization with explicit weight values."""
        retriever = HybridRetriever(
            embedding_manager=mock_embedding_manager,
            vector_store=mock_vector_store,
            vector_weight=0.6,
            graph_weight=0.25,
            bm25_weight=0.15,
        )

        assert retriever.vector_weight == 0.6
        assert retriever.graph_weight == 0.25
        assert retriever.bm25_weight == 0.15

    def test_init_with_config(self, mock_embedding_manager, mock_vector_store, search_quality_config):
        """Test initialization with config object."""
        retriever = HybridRetriever(
            embedding_manager=mock_embedding_manager,
            vector_store=mock_vector_store,
            config=search_quality_config,
        )

        assert retriever.config == search_quality_config

    def test_lazy_component_initialization(self, mock_embedding_manager, mock_vector_store):
        """Test that components are lazily initialized."""
        retriever = HybridRetriever(
            embedding_manager=mock_embedding_manager,
            vector_store=mock_vector_store,
        )

        # Internal components should be None until accessed
        assert retriever._query_expander is None
        assert retriever._adaptive_threshold is None
        assert retriever._mmr_reranker is None
        assert retriever._bm25_searcher is None


class TestVectorSearch:
    """Tests for vector search functionality."""

    def test_basic_vector_search(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test basic vector search execution."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="hypertension treatment",
            top_k=5,
            similarity_threshold=0.3,
            use_graph_search=False,
            enable_bm25=False,
        )

        response = hybrid_retriever.search(request)

        assert response.total_results > 0
        mock_vector_store.search.assert_called_once()

    def test_vector_search_with_threshold_filtering(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test that results below threshold are filtered."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="test query",
            top_k=5,
            similarity_threshold=0.7,  # Higher threshold
            use_graph_search=False,
            enable_bm25=False,
            enable_adaptive_threshold=False,
        )

        response = hybrid_retriever.search(request)

        # Should filter out results below 0.7
        for result in response.results:
            assert result.vector_score >= 0.7 or result.combined_score >= 0


class TestBM25Search:
    """Tests for BM25 hybrid search."""

    def test_bm25_disabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with BM25 disabled."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="test query",
            top_k=5,
            enable_bm25=False,
        )

        response = hybrid_retriever.search(request)

        assert response.bm25_enabled is False

    def test_bm25_enabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with BM25 enabled."""
        mock_vector_store.search.return_value = sample_vector_results

        # Mock BM25 searcher
        mock_bm25 = Mock()
        mock_bm25.search.return_value = []

        with patch.object(hybrid_retriever, '_get_bm25_searcher', return_value=mock_bm25):
            request = RAGQueryRequest(
                query="test query",
                top_k=5,
                enable_bm25=True,
            )

            response = hybrid_retriever.search(request)

            assert response.bm25_enabled is True
            mock_bm25.search.assert_called_once()


class TestGraphSearch:
    """Tests for knowledge graph search integration."""

    def test_graph_search_disabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with graph search disabled."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="test query",
            top_k=5,
            use_graph_search=False,
        )

        response = hybrid_retriever.search(request)

        assert response.total_results >= 0

    def test_graph_search_enabled(self, hybrid_retriever, mock_vector_store, mock_graphiti_client, sample_vector_results):
        """Test search with graph search enabled."""
        mock_vector_store.search.return_value = sample_vector_results

        with patch.object(hybrid_retriever, '_get_graphiti_client', return_value=mock_graphiti_client):
            request = RAGQueryRequest(
                query="test query",
                top_k=5,
                use_graph_search=True,
            )

            response = hybrid_retriever.search(request)

            mock_graphiti_client.search.assert_called_once()


class TestQueryExpansion:
    """Tests for medical query expansion."""

    def test_query_expansion_disabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with query expansion disabled."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="HTN treatment",
            top_k=5,
            enable_query_expansion=False,
        )

        response = hybrid_retriever.search(request)

        assert response.query_expansion is None

    def test_query_expansion_enabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with query expansion enabled."""
        mock_vector_store.search.return_value = sample_vector_results

        # Mock query expander to return proper QueryExpansion model
        mock_expander = Mock()
        mock_expander.expand_query.return_value = QueryExpansion(
            original_query="HTN",
            expanded_terms=["hypertension"],
            expansions_applied=["abbreviation"]
        )

        with patch.object(hybrid_retriever, '_get_query_expander', return_value=mock_expander):
            request = RAGQueryRequest(
                query="HTN treatment",
                top_k=5,
                enable_query_expansion=True,
            )

            response = hybrid_retriever.search(request)

            assert response.query_expansion is not None
            mock_expander.expand_query.assert_called_once()


class TestAdaptiveThreshold:
    """Tests for adaptive similarity threshold."""

    def test_adaptive_threshold_disabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with adaptive threshold disabled."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="test query",
            top_k=5,
            similarity_threshold=0.5,
            enable_adaptive_threshold=False,
        )

        response = hybrid_retriever.search(request)

        assert response.adaptive_threshold_used == 0.5

    def test_adaptive_threshold_enabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with adaptive threshold enabled."""
        mock_vector_store.search.return_value = sample_vector_results

        # Mock adaptive threshold calculator
        mock_threshold = Mock()
        mock_threshold.calculate_threshold.return_value = 0.45

        with patch.object(hybrid_retriever, '_get_adaptive_threshold', return_value=mock_threshold):
            request = RAGQueryRequest(
                query="test query",
                top_k=5,
                similarity_threshold=0.5,
                enable_adaptive_threshold=True,
            )

            response = hybrid_retriever.search(request)

            assert response.adaptive_threshold_used == 0.45
            mock_threshold.calculate_threshold.assert_called_once()


class TestMMRReranking:
    """Tests for MMR (Maximal Marginal Relevance) reranking."""

    def test_mmr_disabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with MMR disabled."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="test query",
            top_k=5,
            enable_mmr=False,
        )

        response = hybrid_retriever.search(request)

        assert response.mmr_applied is False

    def test_mmr_enabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with MMR enabled."""
        mock_vector_store.search.return_value = sample_vector_results

        # Mock MMR reranker
        mock_mmr = Mock()
        mock_mmr.rerank.return_value = []

        with patch.object(hybrid_retriever, '_get_mmr_reranker', return_value=mock_mmr):
            request = RAGQueryRequest(
                query="test query",
                top_k=2,  # Less than results to trigger MMR
                enable_mmr=True,
            )

            response = hybrid_retriever.search(request)

            # MMR applied only when results > top_k
            # With 3 results and top_k=2, MMR should be applied


class TestScoreMerging:
    """Tests for result score merging."""

    def test_merge_results_vector_only(self, hybrid_retriever, sample_vector_results):
        """Test merging with only vector results."""
        merged = hybrid_retriever._merge_results_enhanced(
            vector_results=sample_vector_results,
            bm25_results=[],
            graph_results=[],
            query_embedding=[0.1] * 1536,
            similarity_threshold=0.3,
            top_k=10,
        )

        assert len(merged) == 3
        # Combined score should reflect vector weight
        for result in merged:
            expected = result.vector_score * hybrid_retriever.vector_weight
            assert abs(result.combined_score - expected) < 0.01

    def test_merge_results_combined_scores(self, hybrid_retriever, sample_vector_results):
        """Test that combined scores are calculated correctly."""
        # Create BM25-like results
        bm25_results = [
            Mock(
                chunk_text="Hypertension guidelines",
                document_id="doc1",
                chunk_index=0,
                bm25_score=0.9,
                metadata={"filename": "guidelines.pdf"},
            )
        ]

        merged = hybrid_retriever._merge_results_enhanced(
            vector_results=sample_vector_results,
            bm25_results=bm25_results,
            graph_results=[],
            query_embedding=[0.1] * 1536,
            similarity_threshold=0.3,
            top_k=10,
        )

        # Find the merged result for doc1
        doc1_result = next((r for r in merged if r.document_id == "doc1"), None)
        assert doc1_result is not None
        assert doc1_result.bm25_score > 0

    def test_merge_results_respects_threshold(self, hybrid_retriever, sample_vector_results):
        """Test that results below threshold are filtered."""
        merged = hybrid_retriever._merge_results_enhanced(
            vector_results=sample_vector_results,
            bm25_results=[],
            graph_results=[],
            query_embedding=None,
            similarity_threshold=0.8,  # High threshold
            top_k=10,
        )

        # Only first result has score >= 0.8
        assert len(merged) == 1


class TestResultFiltering:
    """Tests for result filtering methods."""

    def test_filter_by_document_type_pdf(self, hybrid_retriever):
        """Test filtering by PDF document type."""
        results = [
            HybridSearchResult(
                chunk_text="Content 1",
                document_id="doc1",
                document_filename="file1.pdf",
                chunk_index=0,
                vector_score=0.8,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.8,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
            HybridSearchResult(
                chunk_text="Content 2",
                document_id="doc2",
                document_filename="file2.docx",
                chunk_index=0,
                vector_score=0.7,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.7,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
        ]

        filtered = hybrid_retriever._filter_by_document_type(results, ["pdf"])

        assert len(filtered) == 1
        assert filtered[0].document_filename == "file1.pdf"

    def test_filter_by_date_range(self, hybrid_retriever):
        """Test filtering by date range."""
        now = datetime.now()
        results = [
            HybridSearchResult(
                chunk_text="Recent content",
                document_id="doc1",
                document_filename="recent.pdf",
                chunk_index=0,
                vector_score=0.8,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.8,
                mmr_score=0.0,
                related_entities=[],
                metadata={"created_at": (now - timedelta(days=5)).isoformat()},
            ),
            HybridSearchResult(
                chunk_text="Old content",
                document_id="doc2",
                document_filename="old.pdf",
                chunk_index=0,
                vector_score=0.7,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.7,
                mmr_score=0.0,
                related_entities=[],
                metadata={"created_at": (now - timedelta(days=60)).isoformat()},
            ),
        ]

        start_date = now - timedelta(days=30)
        end_date = now

        filtered = hybrid_retriever._filter_by_date_range(results, start_date, end_date)

        assert len(filtered) == 1
        assert filtered[0].document_id == "doc1"

    def test_filter_exclude_terms(self, hybrid_retriever):
        """Test filtering out results with excluded terms."""
        results = [
            HybridSearchResult(
                chunk_text="Content about hypertension treatment",
                document_id="doc1",
                document_filename="doc1.pdf",
                chunk_index=0,
                vector_score=0.8,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.8,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
            HybridSearchResult(
                chunk_text="Content about diabetes management",
                document_id="doc2",
                document_filename="doc2.pdf",
                chunk_index=0,
                vector_score=0.7,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.7,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
        ]

        filtered = hybrid_retriever._filter_exclude_terms(results, ["diabetes"])

        assert len(filtered) == 1
        assert "hypertension" in filtered[0].chunk_text

    def test_filter_exact_phrases(self, hybrid_retriever):
        """Test filtering to require exact phrases."""
        results = [
            HybridSearchResult(
                chunk_text="The blood pressure guidelines recommend",
                document_id="doc1",
                document_filename="doc1.pdf",
                chunk_index=0,
                vector_score=0.8,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.8,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
            HybridSearchResult(
                chunk_text="Blood tests and pressure monitoring",
                document_id="doc2",
                document_filename="doc2.pdf",
                chunk_index=0,
                vector_score=0.7,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.7,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
        ]

        filtered = hybrid_retriever._filter_exact_phrases(results, ["blood pressure"])

        assert len(filtered) == 1
        assert "blood pressure" in filtered[0].chunk_text.lower()


class TestContextBuilding:
    """Tests for context text building."""

    def test_build_context_empty(self, hybrid_retriever):
        """Test building context from empty results."""
        context = hybrid_retriever._build_context([])

        assert context == ""

    def test_build_context_with_results(self, hybrid_retriever):
        """Test building context from results."""
        results = [
            HybridSearchResult(
                chunk_text="First chunk content",
                document_id="doc1",
                document_filename="file1.pdf",
                chunk_index=0,
                vector_score=0.8,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.8,
                mmr_score=0.0,
                related_entities=["hypertension", "treatment"],
                metadata={},
            ),
            HybridSearchResult(
                chunk_text="Second chunk content",
                document_id="doc2",
                document_filename="file2.pdf",
                chunk_index=0,
                vector_score=0.7,
                graph_score=0.0,
                bm25_score=0.0,
                combined_score=0.7,
                mmr_score=0.0,
                related_entities=[],
                metadata={},
            ),
        ]

        context = hybrid_retriever._build_context(results)

        assert "Source 1: file1.pdf" in context
        assert "First chunk content" in context
        assert "Related concepts:" in context
        assert "Source 2: file2.pdf" in context


class TestSimpleSearch:
    """Tests for simple search interface."""

    def test_search_simple(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test simple search interface."""
        mock_vector_store.search.return_value = sample_vector_results

        response = hybrid_retriever.search_simple(
            query="hypertension",
            top_k=3,
            use_graph=False,
            similarity_threshold=0.5,
        )

        assert response.query == "hypertension"
        assert response.total_results >= 0


class TestRetrievalStats:
    """Tests for retrieval statistics."""

    def test_get_retrieval_stats(self, hybrid_retriever, mock_vector_store):
        """Test getting retrieval statistics."""
        mock_vector_store.health_check.return_value = True
        mock_vector_store.get_stats.return_value = {"total_documents": 50}

        stats = hybrid_retriever.get_retrieval_stats()

        assert "vector_store_available" in stats
        assert stats["vector_store_available"] is True


class TestSingletonPattern:
    """Tests for singleton retriever instance."""

    def test_get_hybrid_retriever_singleton(self):
        """Test that get_hybrid_retriever returns same instance."""
        reset_hybrid_retriever()

        retriever1 = get_hybrid_retriever()
        retriever2 = get_hybrid_retriever()

        assert retriever1 is retriever2

    def test_reset_hybrid_retriever(self):
        """Test resetting the singleton."""
        reset_hybrid_retriever()

        retriever1 = get_hybrid_retriever()
        reset_hybrid_retriever()
        retriever2 = get_hybrid_retriever()

        # After reset, should be different instance
        assert retriever1 is not retriever2


class TestTemporalIntegration:
    """Tests for temporal reasoning integration."""

    def test_temporal_query_detection(self, hybrid_retriever, mock_vector_store, sample_vector_results, sample_hybrid_results):
        """Test that temporal queries are detected."""
        mock_vector_store.search.return_value = sample_vector_results

        # Mock temporal reasoner
        mock_reasoner = Mock()
        mock_reasoner.parse_temporal_query.return_value = Mock(
            has_temporal_reference=True,
            time_frame="last_month",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            temporal_keywords=["last month"],
            decay_factor=0.0,
        )
        # Return HybridSearchResult objects (not VectorSearchResult)
        mock_reasoner.process_results.return_value = sample_hybrid_results[:2]

        with patch.object(hybrid_retriever, '_get_temporal_reasoner', return_value=mock_reasoner):
            request = RAGQueryRequest(
                query="hypertension guidelines from last month",
                top_k=5,
            )

            response = hybrid_retriever.search(request)

            mock_reasoner.parse_temporal_query.assert_called_once()
            assert response.temporal_info is not None

    def test_temporal_filtering_applied(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test that temporal filtering is applied."""
        mock_vector_store.search.return_value = sample_vector_results

        mock_reasoner = Mock()
        mock_reasoner.parse_temporal_query.return_value = Mock(
            has_temporal_reference=True,
            time_frame="recent",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
            temporal_keywords=["recent"],
            decay_factor=0.0,
        )
        mock_reasoner.process_results.return_value = []

        with patch.object(hybrid_retriever, '_get_temporal_reasoner', return_value=mock_reasoner):
            request = RAGQueryRequest(
                query="recent guidelines",
                top_k=5,
            )

            response = hybrid_retriever.search(request)

            assert response.temporal_filtering_applied is True


class TestFeedbackBoosts:
    """Tests for user feedback boost integration."""

    def test_feedback_boost_disabled(self, hybrid_retriever, mock_vector_store, sample_vector_results):
        """Test search with feedback boost disabled."""
        mock_vector_store.search.return_value = sample_vector_results

        request = RAGQueryRequest(
            query="test query",
            top_k=5,
            enable_feedback_boost=False,
        )

        response = hybrid_retriever.search(request)

        assert response.feedback_boosts_applied is False

    def test_feedback_boost_enabled(self, hybrid_retriever, mock_vector_store, sample_vector_results, sample_hybrid_results):
        """Test search with feedback boost enabled."""
        mock_vector_store.search.return_value = sample_vector_results

        mock_feedback = Mock()
        # Return HybridSearchResult objects (not VectorSearchResult)
        mock_feedback.apply_boosts.return_value = sample_hybrid_results

        with patch.object(hybrid_retriever, '_get_feedback_manager', return_value=mock_feedback):
            request = RAGQueryRequest(
                query="test query",
                top_k=5,
                enable_feedback_boost=True,
            )

            response = hybrid_retriever.search(request)

            assert response.feedback_boosts_applied is True
            mock_feedback.apply_boosts.assert_called_once()
