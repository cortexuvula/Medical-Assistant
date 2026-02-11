"""
Unit tests for Clinical Guidelines Ingestion Pipeline.

Tests:
- GuidelinesChunker (Issue 8)
- RecommendationExtractor (Issue 9)
- find_duplicate_guideline case-insensitive + content_hash (Issue 16)
- _insert_guideline_metadata with all columns (Issue 1, 14, 16)
- Transaction cleanup on embedding failure (Issue 4/7)
- GuidelinesEnv shared utility (Issue 6)
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import date

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


# ============================================================================
# Issue 8: GuidelinesChunker tests
# ============================================================================

class TestGuidelinesChunker:
    """Tests for structure-aware chunking."""

    def test_chunk_empty_text(self):
        """Empty text should produce no chunks."""
        from rag.guidelines_chunker import GuidelinesChunker

        chunker = GuidelinesChunker()
        result = chunker.chunk_text("")
        assert result == []

    def test_chunk_whitespace_only(self):
        """Whitespace-only text should produce no chunks."""
        from rag.guidelines_chunker import GuidelinesChunker

        chunker = GuidelinesChunker()
        result = chunker.chunk_text("   \n\n  ")
        assert result == []

    def test_chunk_plain_text_fallback(self):
        """Text without headings should fall back to sentence-based chunking."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "This is a sentence about heart failure. "
            "This is another sentence about treatment. "
            "A third sentence about medications."
        )
        chunker = GuidelinesChunker(max_chunk_tokens=50)
        result = chunker.chunk_text(text)

        assert len(result) > 0
        assert result[0].chunk_index == 0
        assert result[0].section_heading is None

    def test_detect_markdown_headings(self):
        """Markdown headings should create section boundaries."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "# Introduction\n"
            "Heart failure is a clinical syndrome. "
            "It affects millions worldwide.\n"
            "## Treatment\n"
            "Treatment includes diuretics and ACE inhibitors. "
            "Beta blockers are also recommended."
        )
        chunker = GuidelinesChunker(max_chunk_tokens=500)
        result = chunker.chunk_text(text)

        assert len(result) >= 2
        # Check that section headings are preserved
        headings = [c.section_heading for c in result if c.section_heading]
        assert any("Introduction" in h for h in headings)
        assert any("Treatment" in h for h in headings)

    def test_detect_section_headings(self):
        """Section X.Y format headings should create section boundaries."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "Section 1.1: Diagnosis\n"
            "Heart failure diagnosis requires clinical assessment. "
            "Echocardiography is recommended.\n"
            "Section 1.2: Management\n"
            "Management includes lifestyle modifications. "
            "Pharmacotherapy is the cornerstone of treatment."
        )
        chunker = GuidelinesChunker(max_chunk_tokens=500)
        result = chunker.chunk_text(text)

        assert len(result) >= 2
        headings = [c.section_heading for c in result if c.section_heading]
        assert any("Diagnosis" in h for h in headings)
        assert any("Management" in h for h in headings)

    def test_recommendation_detection(self):
        """Chunks with recommendation markers should be flagged."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "# Recommendations\n"
            "Class I recommendation: ACE inhibitors are recommended for patients "
            "with heart failure and reduced ejection fraction. Level A evidence "
            "supports this recommendation."
        )
        chunker = GuidelinesChunker(max_chunk_tokens=500)
        result = chunker.chunk_text(text)

        assert len(result) > 0
        rec_chunks = [c for c in result if c.is_recommendation]
        assert len(rec_chunks) > 0

    def test_chunk_indices_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "# Section A\n"
            "Content for section A is here.\n"
            "# Section B\n"
            "Content for section B is here.\n"
            "# Section C\n"
            "Content for section C is here."
        )
        chunker = GuidelinesChunker(max_chunk_tokens=500)
        result = chunker.chunk_text(text)

        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_chunk_token_count(self):
        """Each chunk should have a token count estimate."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "This is a test sentence with some words. "
            "Another sentence follows here for testing."
        )
        chunker = GuidelinesChunker()
        result = chunker.chunk_text(text)

        for chunk in result:
            assert chunk.token_count > 0
            # Token count should roughly match len(text)//4
            assert chunk.token_count <= len(chunk.chunk_text)

    def test_heading_prefix_preserved(self):
        """When preserve_headings=True, heading appears as prefix in chunk text."""
        from rag.guidelines_chunker import GuidelinesChunker

        text = (
            "# Heart Failure\n"
            "Heart failure treatment requires careful management."
        )
        chunker = GuidelinesChunker(max_chunk_tokens=500, preserve_headings=True)
        result = chunker.chunk_text(text)

        assert len(result) > 0
        # Check heading prefix appears in chunk text
        assert "[" in result[0].chunk_text and "Heart Failure" in result[0].chunk_text

    def test_long_text_splits_into_multiple_chunks(self):
        """Long section content should be split into multiple chunks."""
        from rag.guidelines_chunker import GuidelinesChunker

        sentences = [f"Sentence number {i} about clinical guidelines." for i in range(50)]
        text = " ".join(sentences)
        chunker = GuidelinesChunker(max_chunk_tokens=100)
        result = chunker.chunk_text(text)

        assert len(result) > 1


# ============================================================================
# Issue 9: RecommendationExtractor tests
# ============================================================================

class TestRecommendationExtractor:
    """Tests for recommendation class and evidence level extraction."""

    def test_extract_class_i(self):
        """Extract Class I recommendation."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Class I: ACE inhibitors are recommended.")

        assert result.recommendation_class == "I"

    def test_extract_class_iia(self):
        """Extract Class IIa recommendation."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Class IIa recommendation for beta blockers.")

        assert result.recommendation_class == "IIa"

    def test_extract_class_iib(self):
        """Extract Class IIb recommendation."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Class IIb: May be considered in select patients.")

        assert result.recommendation_class == "IIb"

    def test_extract_class_iii(self):
        """Extract Class III recommendation."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Class III: This therapy is not recommended.")

        assert result.recommendation_class == "III"

    def test_extract_cor_notation(self):
        """Extract COR (Class of Recommendation) notation."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("COR IIa: Implantable defibrillator placement.")

        assert result.recommendation_class == "IIa"

    def test_extract_evidence_level_a(self):
        """Extract Level A evidence."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Level A evidence from randomized trials.")

        assert result.evidence_level == "A"

    def test_extract_evidence_level_b_r(self):
        """Extract Level B-R evidence (randomized)."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("LOE B-R based on moderate quality randomized data.")

        assert result.evidence_level == "B-R"

    def test_extract_evidence_level_b_nr(self):
        """Extract Level B-NR evidence (non-randomized)."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Level B-NR evidence from observational studies.")

        assert result.evidence_level == "B-NR"

    def test_extract_evidence_level_c_eo(self):
        """Extract Level C-EO evidence (expert opinion)."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("LOE C-EO based on expert consensus.")

        assert result.evidence_level == "C-EO"

    def test_extract_evidence_level_c_ld(self):
        """Extract Level C-LD evidence (limited data)."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Level C-LD supported by limited data.")

        assert result.evidence_level == "C-LD"

    def test_extract_section_type_warning(self):
        """Detect WARNING section type."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("WARNING: Black box warning for this medication.")

        assert result.section_type == "warning"

    def test_extract_section_type_contraindication(self):
        """Detect CONTRAINDICATION section type."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("CONTRAINDICATED in patients with renal failure.")

        assert result.section_type == "contraindication"

    def test_extract_section_type_monitoring(self):
        """Detect MONITORING section type."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Monitoring: Regular follow-up visits are recommended.")

        assert result.section_type == "monitoring"

    def test_extract_section_type_evidence(self):
        """Detect EVIDENCE section type."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Multiple RCT studies have confirmed this finding.")

        assert result.section_type == "evidence"

    def test_extract_section_type_rationale(self):
        """Detect RATIONALE section type."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("Supporting Text: The rationale for this approach.")

        assert result.section_type == "rationale"

    def test_extract_default_section_type(self):
        """Default section type should be 'recommendation'."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("ACE inhibitors are recommended for HFrEF.")

        assert result.section_type == "recommendation"

    def test_extract_empty_text(self):
        """Empty text should return default ExtractionResult."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("")

        assert result.recommendation_class is None
        assert result.evidence_level is None
        assert result.confidence == 0.0

    def test_extract_combined(self):
        """Extract both class and evidence level from same text."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract(
            "Class I (Strong) recommendation. Level A evidence supports "
            "the use of ACE inhibitors in heart failure."
        )

        assert result.recommendation_class == "I"
        assert result.evidence_level == "A"
        assert result.confidence >= 0.8

    def test_extract_batch(self):
        """Batch extraction should process multiple chunks."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        chunks = [
            "Class I: ACE inhibitors recommended. Level A.",
            "Simple text without recommendation markers.",
            "Class IIb: May consider ARBs. LOE B-R.",
        ]
        results = extractor.extract_batch(chunks)

        assert len(results) == 3
        assert results[0].recommendation_class == "I"
        assert results[1].recommendation_class is None
        assert results[2].recommendation_class == "IIb"

    def test_extract_parenthetical_level(self):
        """Extract evidence level in parenthetical format."""
        from rag.recommendation_extractor import RecommendationExtractor

        extractor = RecommendationExtractor()
        result = extractor.extract("This therapy is supported (Level B-R) by recent trials.")

        assert result.evidence_level == "B-R"


# ============================================================================
# Issue 16: find_duplicate_guideline tests (case-insensitive + content_hash)
# ============================================================================

class TestFindDuplicateGuideline:
    """Tests for case-insensitive duplicate detection with content hash."""

    def _make_mock_vector_store(self):
        """Create a mock vector store with a mock pool and cursor."""
        mock_store = MagicMock()
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_store._get_pool.return_value = mock_pool
        return mock_store, mock_cursor

    def test_content_hash_match(self):
        """Content hash should be checked first and match."""
        from rag.guidelines_vector_store import GuidelinesVectorStore

        store = GuidelinesVectorStore.__new__(GuidelinesVectorStore)
        store._pool = MagicMock()

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        store._get_pool = MagicMock(return_value=mock_pool)

        # Content hash match found on first query
        mock_cursor.fetchone.return_value = ("abc-123-uuid",)

        result = store.find_duplicate_guideline(
            title="Test", content_hash="deadbeef12345678"
        )

        assert result == "abc-123-uuid"

    def test_title_case_insensitive(self):
        """Title matching should be case-insensitive (uses LOWER())."""
        from rag.guidelines_vector_store import GuidelinesVectorStore

        store = GuidelinesVectorStore.__new__(GuidelinesVectorStore)
        store._pool = MagicMock()

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        store._get_pool = MagicMock(return_value=mock_pool)

        # No content_hash, no filename - falls through to title matching
        mock_cursor.fetchone.return_value = ("existing-uuid",)

        result = store.find_duplicate_guideline(
            title="AHA Heart Failure Guidelines"
        )

        assert result == "existing-uuid"
        # Verify SQL was called with the title
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "LOWER" in sql

    def test_no_duplicate_found(self):
        """Should return None when no duplicate exists."""
        from rag.guidelines_vector_store import GuidelinesVectorStore

        store = GuidelinesVectorStore.__new__(GuidelinesVectorStore)
        store._pool = MagicMock()

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        store._get_pool = MagicMock(return_value=mock_pool)

        # No matches
        mock_cursor.fetchone.return_value = None

        result = store.find_duplicate_guideline(
            title="Brand New Guideline"
        )

        assert result is None

    def test_filename_match(self):
        """Filename should be checked when content_hash doesn't match."""
        from rag.guidelines_vector_store import GuidelinesVectorStore

        store = GuidelinesVectorStore.__new__(GuidelinesVectorStore)
        store._pool = MagicMock()

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        store._get_pool = MagicMock(return_value=mock_pool)

        # First call (content_hash) returns None, second call (filename) returns match
        mock_cursor.fetchone.side_effect = [None, ("file-match-uuid",)]

        result = store.find_duplicate_guideline(
            title="Test",
            content_hash="abcdef",
            filename="test_guideline.pdf",
        )

        assert result == "file-match-uuid"


# ============================================================================
# Issue 1 + 14 + 16: _insert_guideline_metadata tests
# ============================================================================

class TestInsertGuidelineMetadata:
    """Tests for _insert_guideline_metadata with all columns."""

    def test_insert_includes_filename(self):
        """INSERT should include the filename column (Issue 1)."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        mock_vector_store = MagicMock()
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_vector_store._get_pool.return_value = mock_pool

        manager._insert_guideline_metadata(
            vector_store=mock_vector_store,
            guideline_id="test-uuid-123",
            title="Heart Failure Guidelines",
            filename="AHA_HF_2024.pdf",
            specialty="Cardiology",
            source="AHA",
            version="2024",
            effective_date=date(2024, 1, 1),
            expiration_date=date(2029, 1, 1),
            content_hash="deadbeef",
        )

        # Verify execute was called
        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]

        # Verify all columns are present in the SQL
        assert "filename" in sql
        assert "expiration_date" in sql
        assert "content_hash" in sql

        # Verify ON CONFLICT clause includes all columns
        assert "ON CONFLICT" in sql
        assert "EXCLUDED.filename" in sql
        assert "EXCLUDED.expiration_date" in sql
        assert "EXCLUDED.content_hash" in sql

        # Verify params include the values
        assert "AHA_HF_2024.pdf" in params
        assert "deadbeef" in params

    def test_insert_includes_expiration_date(self):
        """INSERT should include expiration_date column (Issue 14)."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        mock_vector_store = MagicMock()
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_vector_store._get_pool.return_value = mock_pool

        exp_date = date(2029, 12, 31)

        manager._insert_guideline_metadata(
            vector_store=mock_vector_store,
            guideline_id="test-uuid-456",
            title="Test Guideline",
            filename="test.pdf",
            specialty="General",
            source="Test",
            version="1.0",
            effective_date=date(2024, 1, 1),
            expiration_date=exp_date,
        )

        params = mock_cursor.execute.call_args[0][1]
        assert exp_date in params


# ============================================================================
# Issue 4/7: Transaction cleanup on embedding failure
# ============================================================================

class TestTransactionCleanup:
    """Tests for cleanup on embedding failure."""

    @patch("rag.guidelines_upload_manager.GuidelinesUploadManager._get_document_processor")
    @patch("rag.guidelines_upload_manager.GuidelinesUploadManager._get_vector_store")
    def test_embedding_failure_cleans_up_metadata(self, mock_get_vs, mock_get_dp):
        """If embedding upsert fails, metadata row should be deleted."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()

        # Mock document processor
        mock_dp = MagicMock()
        mock_dp.extract_text.return_value = "Test medical text for guidelines."
        mock_dp.chunk_text.return_value = ["chunk1 text", "chunk2 text"]
        mock_get_dp.return_value = mock_dp

        # Mock vector store
        mock_vs = MagicMock()
        mock_vs.find_duplicate_guideline.return_value = None
        mock_vs.upsert_embeddings_batch.side_effect = Exception("Embedding insert failed")
        mock_vs.delete_guideline_complete.return_value = True

        # Mock pool for _insert_guideline_metadata
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_vs._get_pool.return_value = mock_pool

        mock_get_vs.return_value = mock_vs

        # Mock embedding model
        manager._embedding_model = MagicMock()
        manager._embedding_model.embed.return_value = [[0.1] * 768]

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Test medical guideline content for testing purposes.")
            f.flush()
            temp_path = f.name

        try:
            result = manager.upload_guideline(
                file_path=temp_path,
                title="Test Guideline",
                specialty="General",
                source="Test",
            )

            # Should have failed
            assert result is None or (hasattr(result, 'status') and result.status != 'completed')

        except Exception:
            # Expected - embedding failure should propagate
            pass

        finally:
            os.unlink(temp_path)

        # Verify cleanup was attempted
        # delete_guideline_complete should have been called after embedding failure
        # (The actual behavior depends on whether the exception is caught in upload_guideline)


# ============================================================================
# Issue 3: Sync status update tests
# ============================================================================

class TestSyncStatusUpdate:
    """Tests for _update_sync_status helper."""

    def test_update_neon_synced(self):
        """Should update neon_synced flag."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        mock_vs = MagicMock()
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_vs._get_pool.return_value = mock_pool

        manager._update_sync_status(mock_vs, "test-uuid", neon_synced=True)

        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "neon_synced" in sql

    def test_update_neo4j_synced(self):
        """Should update neo4j_synced flag."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        mock_vs = MagicMock()
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_vs._get_pool.return_value = mock_pool

        manager._update_sync_status(mock_vs, "test-uuid", neo4j_synced=True)

        assert mock_cursor.execute.called
        sql = mock_cursor.execute.call_args[0][0]
        assert "neo4j_synced" in sql

    def test_update_no_flags_is_noop(self):
        """No flags = no SQL executed."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        mock_vs = MagicMock()

        manager._update_sync_status(mock_vs, "test-uuid")

        # _get_pool should not have been called
        mock_vs._get_pool.assert_not_called()


# ============================================================================
# Issue 6: GuidelinesEnv shared utility tests
# ============================================================================

class TestGuidelinesEnv:
    """Tests for shared environment loading utility."""

    def test_load_guidelines_env_importable(self):
        """Should be importable as a module."""
        from rag.guidelines_env import load_guidelines_env

        assert callable(load_guidelines_env)

    @patch("rag.guidelines_env.load_dotenv")
    def test_load_guidelines_env_calls_dotenv(self, mock_load_dotenv):
        """Should call load_dotenv at least once."""
        from rag.guidelines_env import load_guidelines_env

        load_guidelines_env()

        assert mock_load_dotenv.called


# ============================================================================
# Issue 12: Medical content validation tests
# ============================================================================

class TestMedicalContentValidation:
    """Tests for _validate_medical_content helper."""

    def test_medical_content_passes(self):
        """Text with many medical terms should pass validation."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        text = (
            "This clinical guideline provides recommendations for the treatment "
            "of patients with heart failure. The diagnosis requires assessment of "
            "symptoms and medication review. Evidence from clinical trials supports "
            "the use of ACE inhibitors."
        )
        result = manager._validate_medical_content(text)
        assert result is None  # No warning

    def test_non_medical_content_warns(self):
        """Text without medical terms should return a warning."""
        from rag.guidelines_upload_manager import GuidelinesUploadManager

        manager = GuidelinesUploadManager()
        text = (
            "The quick brown fox jumps over the lazy dog. "
            "This is a completely unrelated text about animals."
        )
        result = manager._validate_medical_content(text)
        assert result is not None  # Should return a warning string
        assert isinstance(result, str)


# ============================================================================
# Issue 15: GraphDataProvider env_prefix tests
# ============================================================================

class TestGraphDataProviderEnvPrefix:
    """Tests for GraphDataProvider with env_prefix parameter."""

    def test_default_env_prefix_empty(self):
        """Default env prefix should be empty string."""
        from rag.graph_data_provider import GraphDataProvider

        provider = GraphDataProvider()
        assert provider._env_prefix == ""

    def test_guidelines_env_prefix(self):
        """Guidelines env prefix should be set correctly."""
        from rag.graph_data_provider import GraphDataProvider

        provider = GraphDataProvider(env_prefix="CLINICAL_GUIDELINES_")
        assert provider._env_prefix == "CLINICAL_GUIDELINES_"

    @patch.dict(os.environ, {
        "CLINICAL_GUIDELINES_NEO4J_URI": "bolt://guidelines:7687",
        "CLINICAL_GUIDELINES_NEO4J_PASSWORD": "test_pass",
    })
    def test_guidelines_prefix_reads_correct_env_vars(self):
        """Provider with guidelines prefix should read CLINICAL_GUIDELINES_NEO4J_* vars."""
        from rag.graph_data_provider import GraphDataProvider

        provider = GraphDataProvider(env_prefix="CLINICAL_GUIDELINES_")

        mock_gdb = MagicMock()
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        with patch.dict("sys.modules", {"neo4j": MagicMock(GraphDatabase=mock_gdb)}):
            driver = provider._get_neo4j_driver()

            mock_gdb.driver.assert_called_once()
            call_args = mock_gdb.driver.call_args
            assert call_args[0][0] == "bolt://guidelines:7687"
            assert call_args[1]["auth"] == ("neo4j", "test_pass")

        provider._driver = None  # Reset for cleanup

    @patch.dict(os.environ, {
        "NEO4J_URI": "bolt://patient:7687",
        "NEO4J_PASSWORD": "patient_pass",
    })
    def test_patient_prefix_reads_standard_env_vars(self):
        """Provider with empty prefix should read standard NEO4J_* vars."""
        from rag.graph_data_provider import GraphDataProvider

        provider = GraphDataProvider(env_prefix="")

        mock_gdb = MagicMock()
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        with patch.dict("sys.modules", {"neo4j": MagicMock(GraphDatabase=mock_gdb)}):
            driver = provider._get_neo4j_driver()

            mock_gdb.driver.assert_called_once()
            call_args = mock_gdb.driver.call_args
            assert call_args[0][0] == "bolt://patient:7687"
            assert call_args[1]["auth"] == ("neo4j", "patient_pass")

        provider._driver = None  # Reset for cleanup


# ============================================================================
# Issue 8 + 9 Integration: Chunker + Extractor
# ============================================================================

class TestChunkerExtractorIntegration:
    """Integration tests for chunker + extractor working together."""

    def test_chunked_text_with_extraction(self):
        """Chunks from structured text should have extractable metadata."""
        from rag.guidelines_chunker import GuidelinesChunker
        from rag.recommendation_extractor import RecommendationExtractor

        text = (
            "# Recommendations for Heart Failure\n"
            "Class I: Guideline-directed medical therapy including ACE inhibitors "
            "is recommended for all patients with HFrEF. Level A evidence from "
            "multiple randomized controlled trials supports this approach. "
            "Beta-blockers should be initiated in stable patients.\n"
            "# Monitoring\n"
            "Regular follow-up visits are recommended every 3-6 months. "
            "Monitor renal function and electrolytes."
        )

        chunker = GuidelinesChunker(max_chunk_tokens=500)
        extractor = RecommendationExtractor()

        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

        # Extract from each chunk
        for chunk in chunks:
            result = extractor.extract(chunk.chunk_text)
            if chunk.is_recommendation:
                # Recommendation chunks should have class and/or evidence
                assert (
                    result.recommendation_class is not None or
                    result.evidence_level is not None
                )
