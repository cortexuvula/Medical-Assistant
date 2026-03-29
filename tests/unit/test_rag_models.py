"""
Tests for src/rag/models.py
No network, no Tkinter, no I/O.
"""
import sys
import pytest
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.models import (
    DocumentType, UploadStatus, DocumentMetadata, DocumentChunk,
    RAGDocument, EmbeddingRequest, EmbeddingResponse, VectorSearchQuery,
    VectorSearchResult, GraphSearchResult, HybridSearchResult,
    QueryExpansion, RAGQueryRequest, TemporalInfo, RAGQueryResponse,
    DocumentUploadRequest, DocumentUploadProgress, DocumentListItem, RAGSettings,
)


# ---------------------------------------------------------------------------
# TestDocumentType
# ---------------------------------------------------------------------------

class TestDocumentType:
    def test_member_count(self):
        assert len(DocumentType) == 4

    def test_pdf_value(self):
        assert DocumentType.PDF == "pdf"

    def test_docx_value(self):
        assert DocumentType.DOCX == "docx"

    def test_txt_value(self):
        assert DocumentType.TXT == "txt"

    def test_image_value(self):
        assert DocumentType.IMAGE == "image"

    def test_is_str_enum(self):
        assert isinstance(DocumentType.PDF, str)

    def test_all_values_are_lowercase(self):
        for member in DocumentType:
            assert member.value == member.value.lower()


# ---------------------------------------------------------------------------
# TestUploadStatus
# ---------------------------------------------------------------------------

class TestUploadStatus:
    def test_member_count(self):
        assert len(UploadStatus) == 8

    def test_pending_value(self):
        assert UploadStatus.PENDING == "pending"

    def test_extracting_value(self):
        assert UploadStatus.EXTRACTING == "extracting"

    def test_chunking_value(self):
        assert UploadStatus.CHUNKING == "chunking"

    def test_embedding_value(self):
        assert UploadStatus.EMBEDDING == "embedding"

    def test_syncing_value(self):
        assert UploadStatus.SYNCING == "syncing"

    def test_completed_value(self):
        assert UploadStatus.COMPLETED == "completed"

    def test_failed_value(self):
        assert UploadStatus.FAILED == "failed"

    def test_synced_value(self):
        assert UploadStatus.SYNCED == "synced"

    def test_is_str_enum(self):
        assert isinstance(UploadStatus.PENDING, str)

    def test_all_values_are_lowercase(self):
        for member in UploadStatus:
            assert member.value == member.value.lower()


# ---------------------------------------------------------------------------
# TestDocumentMetadata
# ---------------------------------------------------------------------------

class TestDocumentMetadata:
    def test_title_default_none(self):
        m = DocumentMetadata()
        assert m.title is None

    def test_author_default_none(self):
        m = DocumentMetadata()
        assert m.author is None

    def test_subject_default_none(self):
        m = DocumentMetadata()
        assert m.subject is None

    def test_keywords_default_empty_list(self):
        m = DocumentMetadata()
        assert m.keywords == []

    def test_creation_date_default_none(self):
        m = DocumentMetadata()
        assert m.creation_date is None

    def test_modification_date_default_none(self):
        m = DocumentMetadata()
        assert m.modification_date is None

    def test_language_default_en(self):
        m = DocumentMetadata()
        assert m.language == "en"

    def test_category_default_none(self):
        m = DocumentMetadata()
        assert m.category is None

    def test_custom_tags_default_empty_list(self):
        m = DocumentMetadata()
        assert m.custom_tags == []

    def test_keywords_not_shared_across_instances(self):
        m1 = DocumentMetadata()
        m2 = DocumentMetadata()
        m1.keywords.append("x")
        assert m2.keywords == []

    def test_custom_tags_not_shared_across_instances(self):
        m1 = DocumentMetadata()
        m2 = DocumentMetadata()
        m1.custom_tags.append("tag")
        assert m2.custom_tags == []

    def test_custom_values(self):
        dt = datetime(2024, 1, 15)
        m = DocumentMetadata(
            title="Test Title",
            author="Dr. Smith",
            subject="Cardiology",
            keywords=["heart", "ECG"],
            creation_date=dt,
            language="fr",
            category="clinical",
            custom_tags=["urgent"],
        )
        assert m.title == "Test Title"
        assert m.author == "Dr. Smith"
        assert m.subject == "Cardiology"
        assert m.keywords == ["heart", "ECG"]
        assert m.creation_date == dt
        assert m.language == "fr"
        assert m.category == "clinical"
        assert m.custom_tags == ["urgent"]


# ---------------------------------------------------------------------------
# TestDocumentChunk
# ---------------------------------------------------------------------------

class TestDocumentChunk:
    def test_required_fields_stored(self):
        c = DocumentChunk(chunk_index=0, chunk_text="hello", token_count=1)
        assert c.chunk_index == 0
        assert c.chunk_text == "hello"
        assert c.token_count == 1

    def test_start_page_default_none(self):
        c = DocumentChunk(chunk_index=0, chunk_text="x", token_count=1)
        assert c.start_page is None

    def test_end_page_default_none(self):
        c = DocumentChunk(chunk_index=0, chunk_text="x", token_count=1)
        assert c.end_page is None

    def test_neon_id_default_none(self):
        c = DocumentChunk(chunk_index=0, chunk_text="x", token_count=1)
        assert c.neon_id is None

    def test_embedding_default_none(self):
        c = DocumentChunk(chunk_index=0, chunk_text="x", token_count=1)
        assert c.embedding is None

    def test_optional_fields_set(self):
        c = DocumentChunk(
            chunk_index=3,
            chunk_text="some text",
            token_count=10,
            start_page=1,
            end_page=2,
            neon_id="abc-123",
            embedding=[0.1, 0.2, 0.3],
        )
        assert c.start_page == 1
        assert c.end_page == 2
        assert c.neon_id == "abc-123"
        assert c.embedding == [0.1, 0.2, 0.3]

    def test_chunk_index_zero_valid(self):
        c = DocumentChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert c.chunk_index == 0

    def test_large_token_count(self):
        c = DocumentChunk(chunk_index=99, chunk_text="long text", token_count=9999)
        assert c.token_count == 9999


# ---------------------------------------------------------------------------
# TestRAGDocument
# ---------------------------------------------------------------------------

class TestRAGDocument:
    def test_document_id_is_string(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert isinstance(doc.document_id, str)

    def test_document_id_non_empty(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert len(doc.document_id) > 0

    def test_document_id_unique_per_instance(self):
        doc1 = RAGDocument(filename="a.pdf", file_type=DocumentType.PDF)
        doc2 = RAGDocument(filename="b.pdf", file_type=DocumentType.PDF)
        assert doc1.document_id != doc2.document_id

    def test_filename_stored(self):
        doc = RAGDocument(filename="report.docx", file_type=DocumentType.DOCX)
        assert doc.filename == "report.docx"

    def test_file_type_stored(self):
        # use_enum_values=True means file_type is stored as the string value "pdf"
        doc = RAGDocument(filename="notes.txt", file_type=DocumentType.TXT)
        assert doc.file_type == "txt"

    def test_file_path_default_none(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.file_path is None

    def test_file_size_bytes_default_zero(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.file_size_bytes == 0

    def test_page_count_default_zero(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.page_count == 0

    def test_ocr_required_default_false(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.ocr_required is False

    def test_upload_status_default_pending(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        # use_enum_values=True stores the string value
        assert doc.upload_status == UploadStatus.PENDING.value

    def test_chunk_count_default_zero(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.chunk_count == 0

    def test_neon_synced_default_false(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.neon_synced is False

    def test_graphiti_synced_default_false(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.graphiti_synced is False

    def test_error_message_default_none(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.error_message is None

    def test_metadata_default_is_document_metadata(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert isinstance(doc.metadata, DocumentMetadata)

    def test_metadata_not_shared_across_instances(self):
        doc1 = RAGDocument(filename="a.pdf", file_type=DocumentType.PDF)
        doc2 = RAGDocument(filename="b.pdf", file_type=DocumentType.PDF)
        doc1.metadata.title = "Title A"
        assert doc2.metadata.title is None

    def test_chunks_default_empty_list(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert doc.chunks == []

    def test_chunks_not_shared_across_instances(self):
        doc1 = RAGDocument(filename="a.pdf", file_type=DocumentType.PDF)
        doc2 = RAGDocument(filename="b.pdf", file_type=DocumentType.PDF)
        doc1.chunks.append(DocumentChunk(chunk_index=0, chunk_text="t", token_count=1))
        assert doc2.chunks == []

    def test_created_at_is_datetime(self):
        doc = RAGDocument(filename="x.pdf", file_type=DocumentType.PDF)
        assert isinstance(doc.created_at, datetime)

    def test_custom_filename_and_file_type(self):
        doc = RAGDocument(
            filename="scan.png",
            file_type=DocumentType.IMAGE,
            file_path="/tmp/scan.png",
            file_size_bytes=204800,
            page_count=1,
            ocr_required=True,
            upload_status=UploadStatus.COMPLETED,
            chunk_count=5,
            neon_synced=True,
            graphiti_synced=True,
        )
        assert doc.filename == "scan.png"
        assert doc.file_path == "/tmp/scan.png"
        assert doc.file_size_bytes == 204800
        assert doc.page_count == 1
        assert doc.ocr_required is True
        assert doc.chunk_count == 5
        assert doc.neon_synced is True
        assert doc.graphiti_synced is True


# ---------------------------------------------------------------------------
# TestEmbeddingRequest
# ---------------------------------------------------------------------------

class TestEmbeddingRequest:
    def test_model_default(self):
        req = EmbeddingRequest(texts=["hello"])
        assert req.model == "text-embedding-3-small"

    def test_texts_stored(self):
        req = EmbeddingRequest(texts=["hello", "world"])
        assert req.texts == ["hello", "world"]

    def test_empty_texts_list(self):
        req = EmbeddingRequest(texts=[])
        assert req.texts == []

    def test_custom_model(self):
        req = EmbeddingRequest(texts=["x"], model="text-embedding-ada-002")
        assert req.model == "text-embedding-ada-002"

    def test_single_text(self):
        req = EmbeddingRequest(texts=["only one"])
        assert len(req.texts) == 1
        assert req.texts[0] == "only one"


# ---------------------------------------------------------------------------
# TestEmbeddingResponse
# ---------------------------------------------------------------------------

class TestEmbeddingResponse:
    def test_embeddings_stored(self):
        resp = EmbeddingResponse(embeddings=[[0.1, 0.2]], model="m", total_tokens=5)
        assert resp.embeddings == [[0.1, 0.2]]

    def test_model_stored(self):
        resp = EmbeddingResponse(embeddings=[], model="text-embedding-3-small", total_tokens=0)
        assert resp.model == "text-embedding-3-small"

    def test_total_tokens_stored(self):
        resp = EmbeddingResponse(embeddings=[], model="m", total_tokens=42)
        assert resp.total_tokens == 42

    def test_multiple_embeddings(self):
        vecs = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        resp = EmbeddingResponse(embeddings=vecs, model="m", total_tokens=10)
        assert len(resp.embeddings) == 2
        assert resp.embeddings[1] == [0.4, 0.5, 0.6]

    def test_zero_total_tokens(self):
        resp = EmbeddingResponse(embeddings=[], model="m", total_tokens=0)
        assert resp.total_tokens == 0


# ---------------------------------------------------------------------------
# TestVectorSearchQuery
# ---------------------------------------------------------------------------

class TestVectorSearchQuery:
    def test_query_text_stored(self):
        q = VectorSearchQuery(query_text="chest pain")
        assert q.query_text == "chest pain"

    def test_query_embedding_default_none(self):
        q = VectorSearchQuery(query_text="x")
        assert q.query_embedding is None

    def test_top_k_default(self):
        q = VectorSearchQuery(query_text="x")
        assert q.top_k == 10

    def test_similarity_threshold_default(self):
        q = VectorSearchQuery(query_text="x")
        assert q.similarity_threshold == pytest.approx(0.7)

    def test_filter_document_ids_default_none(self):
        q = VectorSearchQuery(query_text="x")
        assert q.filter_document_ids is None

    def test_filter_metadata_default_none(self):
        q = VectorSearchQuery(query_text="x")
        assert q.filter_metadata is None

    def test_custom_top_k(self):
        q = VectorSearchQuery(query_text="x", top_k=5)
        assert q.top_k == 5

    def test_custom_similarity_threshold(self):
        q = VectorSearchQuery(query_text="x", similarity_threshold=0.9)
        assert q.similarity_threshold == pytest.approx(0.9)

    def test_custom_filter_document_ids(self):
        q = VectorSearchQuery(query_text="x", filter_document_ids=["id1", "id2"])
        assert q.filter_document_ids == ["id1", "id2"]

    def test_custom_filter_metadata(self):
        q = VectorSearchQuery(query_text="x", filter_metadata={"category": "clinical"})
        assert q.filter_metadata == {"category": "clinical"}

    def test_custom_query_embedding(self):
        q = VectorSearchQuery(query_text="x", query_embedding=[0.1, 0.2])
        assert q.query_embedding == [0.1, 0.2]


# ---------------------------------------------------------------------------
# TestVectorSearchResult
# ---------------------------------------------------------------------------

class TestVectorSearchResult:
    def test_required_fields_stored(self):
        r = VectorSearchResult(
            document_id="doc-1",
            chunk_index=0,
            chunk_text="some text",
            similarity_score=0.85,
        )
        assert r.document_id == "doc-1"
        assert r.chunk_index == 0
        assert r.chunk_text == "some text"
        assert r.similarity_score == pytest.approx(0.85)

    def test_metadata_default_none(self):
        r = VectorSearchResult(
            document_id="doc-1",
            chunk_index=0,
            chunk_text="text",
            similarity_score=0.5,
        )
        assert r.metadata is None

    def test_metadata_custom(self):
        r = VectorSearchResult(
            document_id="doc-1",
            chunk_index=0,
            chunk_text="text",
            similarity_score=0.5,
            metadata={"page": 3},
        )
        assert r.metadata == {"page": 3}


# ---------------------------------------------------------------------------
# TestGraphSearchResult
# ---------------------------------------------------------------------------

class TestGraphSearchResult:
    def test_required_fields_stored(self):
        r = GraphSearchResult(entity_name="Metformin", entity_type="Drug", fact="lowers blood sugar")
        assert r.entity_name == "Metformin"
        assert r.entity_type == "Drug"
        assert r.fact == "lowers blood sugar"

    def test_source_document_id_default_none(self):
        r = GraphSearchResult(entity_name="A", entity_type="B", fact="C")
        assert r.source_document_id is None

    def test_relevance_score_default_zero(self):
        r = GraphSearchResult(entity_name="A", entity_type="B", fact="C")
        assert r.relevance_score == pytest.approx(0.0)

    def test_custom_source_and_score(self):
        r = GraphSearchResult(
            entity_name="Aspirin",
            entity_type="Drug",
            fact="anti-platelet",
            source_document_id="doc-99",
            relevance_score=0.95,
        )
        assert r.source_document_id == "doc-99"
        assert r.relevance_score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# TestHybridSearchResult
# ---------------------------------------------------------------------------

class TestHybridSearchResult:
    def _make(self, **kwargs):
        defaults = dict(
            chunk_text="text",
            document_id="doc-1",
            document_filename="report.pdf",
            chunk_index=0,
        )
        defaults.update(kwargs)
        return HybridSearchResult(**defaults)

    def test_required_fields_stored(self):
        r = self._make()
        assert r.chunk_text == "text"
        assert r.document_id == "doc-1"
        assert r.document_filename == "report.pdf"
        assert r.chunk_index == 0

    def test_vector_score_default_zero(self):
        assert self._make().vector_score == pytest.approx(0.0)

    def test_graph_score_default_zero(self):
        assert self._make().graph_score == pytest.approx(0.0)

    def test_bm25_score_default_zero(self):
        assert self._make().bm25_score == pytest.approx(0.0)

    def test_combined_score_default_zero(self):
        assert self._make().combined_score == pytest.approx(0.0)

    def test_mmr_score_default_zero(self):
        assert self._make().mmr_score == pytest.approx(0.0)

    def test_feedback_boost_default_zero(self):
        assert self._make().feedback_boost == pytest.approx(0.0)

    def test_related_entities_default_empty(self):
        assert self._make().related_entities == []

    def test_metadata_default_none(self):
        assert self._make().metadata is None

    def test_embedding_default_none(self):
        assert self._make().embedding is None

    def test_related_entities_not_shared(self):
        r1 = self._make()
        r2 = self._make()
        r1.related_entities.append("entity")
        assert r2.related_entities == []

    def test_custom_scores(self):
        r = self._make(
            vector_score=0.8,
            graph_score=0.6,
            bm25_score=0.5,
            combined_score=0.7,
            mmr_score=0.75,
            feedback_boost=0.1,
        )
        assert r.vector_score == pytest.approx(0.8)
        assert r.graph_score == pytest.approx(0.6)
        assert r.bm25_score == pytest.approx(0.5)
        assert r.combined_score == pytest.approx(0.7)
        assert r.mmr_score == pytest.approx(0.75)
        assert r.feedback_boost == pytest.approx(0.1)

    def test_metadata_and_embedding_set(self):
        r = self._make(metadata={"page": 1}, embedding=[0.1, 0.2])
        assert r.metadata == {"page": 1}
        assert r.embedding == [0.1, 0.2]


# ---------------------------------------------------------------------------
# TestQueryExpansion
# ---------------------------------------------------------------------------

class TestQueryExpansion:
    def test_original_query_stored(self):
        qe = QueryExpansion(original_query="hypertension treatment")
        assert qe.original_query == "hypertension treatment"

    def test_expanded_terms_default_empty(self):
        qe = QueryExpansion(original_query="q")
        assert qe.expanded_terms == []

    def test_abbreviation_expansions_default_empty(self):
        qe = QueryExpansion(original_query="q")
        assert qe.abbreviation_expansions == {}

    def test_synonym_expansions_default_empty(self):
        qe = QueryExpansion(original_query="q")
        assert qe.synonym_expansions == {}

    def test_expanded_query_default_empty_string(self):
        qe = QueryExpansion(original_query="q")
        assert qe.expanded_query == ""

    def test_get_all_search_terms_no_expansions(self):
        qe = QueryExpansion(original_query="hypertension")
        terms = qe.get_all_search_terms()
        assert "hypertension" in terms
        assert len(terms) == 1

    def test_get_all_search_terms_with_expanded_terms(self):
        qe = QueryExpansion(
            original_query="HTN",
            expanded_terms=["hypertension", "high blood pressure"],
        )
        terms = qe.get_all_search_terms()
        assert "HTN" in terms
        assert "hypertension" in terms
        assert "high blood pressure" in terms
        assert len(terms) == 3

    def test_get_all_search_terms_with_abbreviation_expansions(self):
        qe = QueryExpansion(
            original_query="MI",
            abbreviation_expansions={"MI": ["myocardial infarction", "heart attack"]},
        )
        terms = qe.get_all_search_terms()
        assert "MI" in terms
        assert "myocardial infarction" in terms
        assert "heart attack" in terms

    def test_get_all_search_terms_with_synonym_expansions(self):
        qe = QueryExpansion(
            original_query="hypertension",
            synonym_expansions={"hypertension": ["high blood pressure", "elevated BP"]},
        )
        terms = qe.get_all_search_terms()
        assert "hypertension" in terms
        assert "high blood pressure" in terms
        assert "elevated BP" in terms

    def test_get_all_search_terms_combined(self):
        qe = QueryExpansion(
            original_query="HTN",
            expanded_terms=["hypertension"],
            abbreviation_expansions={"HTN": ["high blood pressure"]},
            synonym_expansions={"hypertension": ["elevated BP"]},
        )
        terms = qe.get_all_search_terms()
        assert "HTN" in terms
        assert "hypertension" in terms
        assert "high blood pressure" in terms
        assert "elevated BP" in terms

    def test_get_all_search_terms_deduplication(self):
        qe = QueryExpansion(
            original_query="hypertension",
            expanded_terms=["hypertension", "hypertension"],
            abbreviation_expansions={"HTN": ["hypertension"]},
            synonym_expansions={"hypertension": ["hypertension"]},
        )
        terms = qe.get_all_search_terms()
        assert terms.count("hypertension") == 1

    def test_get_all_search_terms_returns_list(self):
        qe = QueryExpansion(original_query="x")
        assert isinstance(qe.get_all_search_terms(), list)

    def test_get_all_search_terms_multiple_abbreviation_keys(self):
        qe = QueryExpansion(
            original_query="query",
            abbreviation_expansions={
                "MI": ["myocardial infarction"],
                "HTN": ["hypertension"],
            },
        )
        terms = qe.get_all_search_terms()
        assert "myocardial infarction" in terms
        assert "hypertension" in terms


# ---------------------------------------------------------------------------
# TestRAGQueryRequest
# ---------------------------------------------------------------------------

class TestRAGQueryRequest:
    def test_query_stored(self):
        r = RAGQueryRequest(query="what is metformin?")
        assert r.query == "what is metformin?"

    def test_top_k_default(self):
        r = RAGQueryRequest(query="q")
        assert r.top_k == 5

    def test_use_graph_search_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.use_graph_search is True

    def test_similarity_threshold_default(self):
        r = RAGQueryRequest(query="q")
        assert r.similarity_threshold == pytest.approx(0.7)

    def test_include_metadata_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.include_metadata is True

    def test_enable_query_expansion_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.enable_query_expansion is True

    def test_enable_adaptive_threshold_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.enable_adaptive_threshold is True

    def test_enable_bm25_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.enable_bm25 is True

    def test_enable_mmr_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.enable_mmr is True

    def test_enable_feedback_boost_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.enable_feedback_boost is True

    def test_enable_temporal_reasoning_default_true(self):
        r = RAGQueryRequest(query="q")
        assert r.enable_temporal_reasoning is True

    def test_custom_query_and_top_k(self):
        r = RAGQueryRequest(query="drug interactions", top_k=10)
        assert r.query == "drug interactions"
        assert r.top_k == 10

    def test_flags_can_be_disabled(self):
        r = RAGQueryRequest(
            query="q",
            use_graph_search=False,
            enable_query_expansion=False,
            enable_bm25=False,
            enable_mmr=False,
        )
        assert r.use_graph_search is False
        assert r.enable_query_expansion is False
        assert r.enable_bm25 is False
        assert r.enable_mmr is False


# ---------------------------------------------------------------------------
# TestTemporalInfo
# ---------------------------------------------------------------------------

class TestTemporalInfo:
    def test_has_temporal_reference_default_false(self):
        t = TemporalInfo()
        assert t.has_temporal_reference is False

    def test_time_frame_default_none(self):
        t = TemporalInfo()
        assert t.time_frame is None

    def test_start_date_default_none(self):
        t = TemporalInfo()
        assert t.start_date is None

    def test_end_date_default_none(self):
        t = TemporalInfo()
        assert t.end_date is None

    def test_temporal_keywords_default_empty_list(self):
        t = TemporalInfo()
        assert t.temporal_keywords == []

    def test_decay_applied_default_false(self):
        t = TemporalInfo()
        assert t.decay_applied is False

    def test_custom_values(self):
        t = TemporalInfo(
            has_temporal_reference=True,
            time_frame="last 6 months",
            start_date="2024-01-01",
            end_date="2024-06-30",
            temporal_keywords=["recent", "last year"],
            decay_applied=True,
        )
        assert t.has_temporal_reference is True
        assert t.time_frame == "last 6 months"
        assert t.start_date == "2024-01-01"
        assert t.end_date == "2024-06-30"
        assert t.temporal_keywords == ["recent", "last year"]
        assert t.decay_applied is True


# ---------------------------------------------------------------------------
# TestRAGQueryResponse
# ---------------------------------------------------------------------------

class TestRAGQueryResponse:
    def _make_result(self):
        return HybridSearchResult(
            chunk_text="result text",
            document_id="doc-1",
            document_filename="doc.pdf",
            chunk_index=0,
        )

    def test_required_fields_stored(self):
        resp = RAGQueryResponse(
            query="my query",
            results=[self._make_result()],
            total_results=1,
            processing_time_ms=42.5,
            context_text="context",
        )
        assert resp.query == "my query"
        assert len(resp.results) == 1
        assert resp.total_results == 1
        assert resp.processing_time_ms == pytest.approx(42.5)
        assert resp.context_text == "context"

    def test_query_expansion_default_none(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.query_expansion is None

    def test_adaptive_threshold_used_default_none(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.adaptive_threshold_used is None

    def test_bm25_enabled_default_false(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.bm25_enabled is False

    def test_mmr_applied_default_false(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.mmr_applied is False

    def test_feedback_boosts_applied_default_false(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.feedback_boosts_applied is False

    def test_temporal_info_default_none(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.temporal_info is None

    def test_temporal_filtering_applied_default_false(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=1.0, context_text="",
        )
        assert resp.temporal_filtering_applied is False

    def test_optional_fields_set(self):
        qe = QueryExpansion(original_query="q")
        ti = TemporalInfo(has_temporal_reference=True)
        resp = RAGQueryResponse(
            query="q",
            results=[],
            total_results=0,
            processing_time_ms=10.0,
            context_text="ctx",
            query_expansion=qe,
            adaptive_threshold_used=0.65,
            bm25_enabled=True,
            mmr_applied=True,
            feedback_boosts_applied=True,
            temporal_info=ti,
            temporal_filtering_applied=True,
        )
        assert resp.query_expansion is qe
        assert resp.adaptive_threshold_used == pytest.approx(0.65)
        assert resp.bm25_enabled is True
        assert resp.mmr_applied is True
        assert resp.feedback_boosts_applied is True
        assert resp.temporal_info is ti
        assert resp.temporal_filtering_applied is True

    def test_empty_results_list(self):
        resp = RAGQueryResponse(
            query="q", results=[], total_results=0,
            processing_time_ms=0.5, context_text="",
        )
        assert resp.results == []


# ---------------------------------------------------------------------------
# TestDocumentUploadRequest
# ---------------------------------------------------------------------------

class TestDocumentUploadRequest:
    def test_file_paths_stored(self):
        req = DocumentUploadRequest(file_paths=["/tmp/a.pdf", "/tmp/b.pdf"])
        assert req.file_paths == ["/tmp/a.pdf", "/tmp/b.pdf"]

    def test_category_default_none(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.category is None

    def test_custom_tags_default_empty(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.custom_tags == []

    def test_enable_ocr_default_true(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.enable_ocr is True

    def test_enable_graph_default_true(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.enable_graph is True

    def test_custom_values(self):
        req = DocumentUploadRequest(
            file_paths=["/tmp/doc.txt"],
            category="research",
            custom_tags=["important"],
            enable_ocr=False,
            enable_graph=False,
        )
        assert req.category == "research"
        assert req.custom_tags == ["important"]
        assert req.enable_ocr is False
        assert req.enable_graph is False

    def test_empty_file_paths(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.file_paths == []


# ---------------------------------------------------------------------------
# TestDocumentUploadProgress
# ---------------------------------------------------------------------------

class TestDocumentUploadProgress:
    def test_required_fields_stored(self):
        p = DocumentUploadProgress(
            document_id="doc-1",
            filename="report.pdf",
            status=UploadStatus.EXTRACTING,
        )
        assert p.document_id == "doc-1"
        assert p.filename == "report.pdf"

    def test_status_stored(self):
        p = DocumentUploadProgress(
            document_id="d", filename="f.pdf", status=UploadStatus.EXTRACTING
        )
        # DocumentUploadProgress does not use use_enum_values, so enum is preserved
        assert p.status == UploadStatus.EXTRACTING

    def test_progress_percent_default_zero(self):
        p = DocumentUploadProgress(
            document_id="d", filename="f.pdf", status=UploadStatus.PENDING
        )
        assert p.progress_percent == pytest.approx(0.0)

    def test_current_step_default_empty_string(self):
        p = DocumentUploadProgress(
            document_id="d", filename="f.pdf", status=UploadStatus.PENDING
        )
        assert p.current_step == ""

    def test_error_message_default_none(self):
        p = DocumentUploadProgress(
            document_id="d", filename="f.pdf", status=UploadStatus.PENDING
        )
        assert p.error_message is None

    def test_custom_values(self):
        p = DocumentUploadProgress(
            document_id="doc-99",
            filename="scan.png",
            status=UploadStatus.FAILED,
            progress_percent=50.0,
            current_step="OCR processing",
            error_message="OCR timeout",
        )
        assert p.progress_percent == pytest.approx(50.0)
        assert p.current_step == "OCR processing"
        assert p.error_message == "OCR timeout"

    def test_completed_progress(self):
        p = DocumentUploadProgress(
            document_id="d", filename="f.pdf",
            status=UploadStatus.COMPLETED, progress_percent=100.0,
        )
        assert p.progress_percent == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# TestDocumentListItem
# ---------------------------------------------------------------------------

class TestDocumentListItem:
    def _make(self, **kwargs):
        dt = datetime(2024, 6, 1, 12, 0, 0)
        defaults = dict(
            document_id="doc-1",
            filename="report.pdf",
            file_type=DocumentType.PDF,
            file_size_bytes=1024,
            page_count=3,
            chunk_count=10,
            upload_status=UploadStatus.COMPLETED,
            neon_synced=True,
            graphiti_synced=False,
            created_at=dt,
        )
        defaults.update(kwargs)
        return DocumentListItem(**defaults)

    def test_document_id_stored(self):
        assert self._make().document_id == "doc-1"

    def test_filename_stored(self):
        assert self._make().filename == "report.pdf"

    def test_file_size_bytes_stored(self):
        assert self._make().file_size_bytes == 1024

    def test_page_count_stored(self):
        assert self._make().page_count == 3

    def test_chunk_count_stored(self):
        assert self._make().chunk_count == 10

    def test_neon_synced_stored(self):
        assert self._make().neon_synced is True

    def test_graphiti_synced_stored(self):
        assert self._make().graphiti_synced is False

    def test_created_at_is_datetime(self):
        assert isinstance(self._make().created_at, datetime)

    def test_file_type_stored(self):
        item = self._make()
        # DocumentListItem has no use_enum_values; enum is preserved
        assert item.file_type == DocumentType.PDF

    def test_upload_status_stored(self):
        item = self._make()
        assert item.upload_status == UploadStatus.COMPLETED

    def test_category_default_none(self):
        assert self._make().category is None

    def test_tags_default_empty(self):
        assert self._make().tags == []

    def test_custom_category_and_tags(self):
        item = self._make(category="clinical", tags=["urgent", "review"])
        assert item.category == "clinical"
        assert item.tags == ["urgent", "review"]

    def test_tags_not_shared_across_instances(self):
        item1 = self._make()
        item2 = self._make()
        item1.tags.append("tag")
        assert item2.tags == []


# ---------------------------------------------------------------------------
# TestRAGSettings
# ---------------------------------------------------------------------------

class TestRAGSettings:
    def test_embedding_model_default(self):
        s = RAGSettings()
        assert s.embedding_model == "text-embedding-3-small"

    def test_chunk_size_tokens_default(self):
        s = RAGSettings()
        assert s.chunk_size_tokens == 500

    def test_chunk_overlap_tokens_default(self):
        s = RAGSettings()
        assert s.chunk_overlap_tokens == 50

    def test_default_top_k(self):
        s = RAGSettings()
        assert s.default_top_k == 5

    def test_default_similarity_threshold(self):
        s = RAGSettings()
        assert s.default_similarity_threshold == pytest.approx(0.7)

    def test_neon_database_url_default_none(self):
        s = RAGSettings()
        assert s.neon_database_url is None

    def test_neon_pool_size_default(self):
        s = RAGSettings()
        assert s.neon_pool_size == 5

    def test_embedding_dimensions_default(self):
        s = RAGSettings()
        assert s.embedding_dimensions == 1536

    def test_embedding_batch_size_default(self):
        s = RAGSettings()
        assert s.embedding_batch_size == 100

    def test_max_chunks_per_document_default(self):
        s = RAGSettings()
        assert s.max_chunks_per_document == 1000

    def test_enable_graph_search_default_true(self):
        s = RAGSettings()
        assert s.enable_graph_search is True

    def test_enable_adaptive_threshold_default_true(self):
        s = RAGSettings()
        assert s.enable_adaptive_threshold is True

    def test_enable_query_expansion_default_true(self):
        s = RAGSettings()
        assert s.enable_query_expansion is True

    def test_enable_bm25_default_true(self):
        s = RAGSettings()
        assert s.enable_bm25 is True

    def test_enable_mmr_default_true(self):
        s = RAGSettings()
        assert s.enable_mmr is True

    def test_supported_extensions_is_list(self):
        s = RAGSettings()
        assert isinstance(s.supported_extensions, list)

    def test_supported_extensions_contains_pdf(self):
        s = RAGSettings()
        assert ".pdf" in s.supported_extensions

    def test_supported_extensions_contains_docx(self):
        s = RAGSettings()
        assert ".docx" in s.supported_extensions

    def test_supported_extensions_contains_txt(self):
        s = RAGSettings()
        assert ".txt" in s.supported_extensions

    def test_supported_extensions_contains_image_types(self):
        s = RAGSettings()
        for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            assert ext in s.supported_extensions, f"Missing extension: {ext}"

    def test_supported_extensions_not_shared_across_instances(self):
        s1 = RAGSettings()
        s2 = RAGSettings()
        s1.supported_extensions.append(".xyz")
        assert ".xyz" not in s2.supported_extensions

    def test_hnsw_m_default(self):
        s = RAGSettings()
        assert s.hnsw_m == 16

    def test_hnsw_ef_construction_default(self):
        s = RAGSettings()
        assert s.hnsw_ef_construction == 64

    def test_hnsw_ef_search_default(self):
        s = RAGSettings()
        assert s.hnsw_ef_search == 40

    def test_enable_ocr_default_true(self):
        s = RAGSettings()
        assert s.enable_ocr is True

    def test_ocr_language_default(self):
        s = RAGSettings()
        assert s.ocr_language == "eng"

    def test_max_file_size_mb_default(self):
        s = RAGSettings()
        assert s.max_file_size_mb == 50

    def test_custom_override(self):
        s = RAGSettings(
            embedding_model="text-embedding-ada-002",
            chunk_size_tokens=256,
            default_top_k=10,
            enable_bm25=False,
        )
        assert s.embedding_model == "text-embedding-ada-002"
        assert s.chunk_size_tokens == 256
        assert s.default_top_k == 10
        assert s.enable_bm25 is False

    def test_graphiti_fields_default_none(self):
        s = RAGSettings()
        assert s.graphiti_neo4j_uri is None
        assert s.graphiti_neo4j_user is None
        assert s.graphiti_neo4j_password is None

    def test_weight_defaults(self):
        s = RAGSettings()
        assert s.vector_weight == pytest.approx(0.5)
        assert s.bm25_weight == pytest.approx(0.3)
        assert s.graph_weight == pytest.approx(0.2)

    def test_mmr_lambda_default(self):
        s = RAGSettings()
        assert s.mmr_lambda == pytest.approx(0.7)

    def test_adaptive_threshold_bounds(self):
        s = RAGSettings()
        assert s.adaptive_min_threshold == pytest.approx(0.2)
        assert s.adaptive_max_threshold == pytest.approx(0.8)
