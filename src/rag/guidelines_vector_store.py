"""
Clinical Guidelines Vector Store for Neon PostgreSQL.

Separate vector store for clinical guidelines, isolated from patient documents.
Uses pgvector with HNSW indexing for fast similarity search.

Architecture Note:
    This store is intentionally SEPARATE from the main RAG system to ensure:
    1. Patient data isolation - guidelines cannot access patient documents
    2. Independent scaling - guidelines can be managed separately
    3. Compliance - different retention/audit policies can apply
"""

import json
import logging
import os
import pathlib
from typing import Any, Optional

from dotenv import load_dotenv
from utils.structured_logging import timed

from src.rag.guidelines_models import GuidelineSearchResult


# Load environment variables from multiple possible locations
def _load_env():
    """Load .env from multiple possible locations."""
    paths = []
    try:
        from managers.data_folder_manager import data_folder_manager
        paths.append(data_folder_manager.env_file_path)  # AppData / Application Support
    except Exception:
        pass
    paths.extend([
        pathlib.Path(__file__).parent.parent.parent / '.env',  # Project root
        pathlib.Path.cwd() / '.env',  # Current working directory
    ])

    for p in paths:
        try:
            if p.exists():
                load_dotenv(dotenv_path=str(p))
                return
        except Exception:
            pass
    load_dotenv()  # Try default search

_load_env()

logger = logging.getLogger(__name__)

# Default HNSW search parameter for guidelines (can be lower than main RAG)
DEFAULT_HNSW_EF_SEARCH = 40


class GuidelinesVectorStore:
    """Vector store for clinical guidelines using Neon PostgreSQL with pgvector.

    This is a SEPARATE store from the main document store to ensure data isolation.
    It uses the CLINICAL_GUIDELINES_DATABASE_URL environment variable.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        pool_size: int = 3,
    ):
        """Initialize Guidelines vector store.

        Args:
            connection_string: PostgreSQL connection string for guidelines DB
            pool_size: Connection pool size (smaller than main RAG)
        """
        self._connection_string = connection_string
        self._pool_size = pool_size
        self._pool = None

    def _get_connection_string(self) -> str:
        """Get connection string from config or environment."""
        if self._connection_string:
            return self._connection_string

        # Try environment variable (SEPARATE from main RAG)
        conn_str = os.environ.get("CLINICAL_GUIDELINES_DATABASE_URL")
        if conn_str:
            return conn_str

        # Try settings
        try:
            from src.settings.settings import SETTINGS
            guidelines_settings = SETTINGS.get("clinical_guidelines", {})
            conn_str = guidelines_settings.get("database_url")
            if conn_str:
                return conn_str
        except Exception:
            pass

        raise ValueError(
            "Clinical Guidelines database connection string not found. "
            "Set CLINICAL_GUIDELINES_DATABASE_URL environment variable or configure in settings."
        )

    def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import psycopg
                logger.debug(f"psycopg loaded from: {psycopg.__file__}")
            except ImportError as e:
                logger.error(f"Failed to import psycopg: {e}")
                raise ImportError(
                    "psycopg is required for Guidelines vector store. "
                    f"Install with: pip install 'psycopg[binary]'. Error: {e}"
                )

            try:
                import psycopg_pool
            except ImportError as e:
                logger.error(f"Failed to import psycopg_pool: {e}")
                raise ImportError(
                    "psycopg_pool is required for Guidelines vector store. "
                    f"Install with: pip install 'psycopg[binary]'. Error: {e}"
                )

            conn_str = self._get_connection_string()
            self._pool = psycopg_pool.ConnectionPool(
                conn_str,
                min_size=1,
                max_size=self._pool_size,
                open=True,
            )
            logger.info("Guidelines vector store connection pool created")

        return self._pool

    def _ensure_pgvector(self, conn):
        """Ensure pgvector extension and register types."""
        try:
            from pgvector.psycopg import register_vector
            register_vector(conn)
        except ImportError:
            logger.warning("pgvector package not installed, vector operations may fail")

    def upsert_embedding(
        self,
        guideline_id: str,
        chunk_index: int,
        chunk_text: str,
        embedding: list[float],
        section_type: str = "recommendation",
        recommendation_class: Optional[str] = None,
        evidence_level: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """Upsert a single guideline embedding.

        Args:
            guideline_id: UUID of the guideline document
            chunk_index: Index of the chunk within the document
            chunk_text: Text content of the chunk
            embedding: Embedding vector
            section_type: Type of section (recommendation, warning, evidence)
            recommendation_class: Recommendation strength (I, IIa, IIb, III)
            evidence_level: Evidence level (A, B, C)
            metadata: Optional additional metadata

        Returns:
            ID of the inserted/updated row
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            self._ensure_pgvector(conn)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO guideline_embeddings
                    (guideline_id, chunk_index, chunk_text, embedding,
                     section_type, recommendation_class, evidence_level, metadata)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (guideline_id, chunk_index)
                    DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        section_type = EXCLUDED.section_type,
                        recommendation_class = EXCLUDED.recommendation_class,
                        evidence_level = EXCLUDED.evidence_level,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        guideline_id,
                        chunk_index,
                        chunk_text,
                        embedding,
                        section_type,
                        recommendation_class,
                        evidence_level,
                        json.dumps(metadata) if metadata else None,
                    )
                )
                result = cur.fetchone()
                conn.commit()
                return result[0] if result else None

    def upsert_embeddings_batch(
        self,
        guideline_id: str,
        chunks: list[tuple],
    ) -> list[int]:
        """Upsert multiple embeddings for a guideline.

        Args:
            guideline_id: UUID of the guideline document
            chunks: List of tuples containing:
                (chunk_index, chunk_text, embedding, section_type,
                 recommendation_class, evidence_level, metadata)

        Returns:
            List of inserted/updated row IDs
        """
        if not chunks:
            return []

        pool = self._get_pool()
        ids = []

        with pool.connection() as conn:
            self._ensure_pgvector(conn)

            with conn.cursor() as cur:
                for chunk in chunks:
                    (chunk_index, chunk_text, embedding, section_type,
                     recommendation_class, evidence_level, metadata) = chunk

                    cur.execute(
                        """
                        INSERT INTO guideline_embeddings
                        (guideline_id, chunk_index, chunk_text, embedding,
                         section_type, recommendation_class, evidence_level, metadata)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (guideline_id, chunk_index)
                        DO UPDATE SET
                            chunk_text = EXCLUDED.chunk_text,
                            embedding = EXCLUDED.embedding,
                            section_type = EXCLUDED.section_type,
                            recommendation_class = EXCLUDED.recommendation_class,
                            evidence_level = EXCLUDED.evidence_level,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        RETURNING id
                        """,
                        (
                            guideline_id,
                            chunk_index,
                            chunk_text,
                            embedding,
                            section_type,
                            recommendation_class,
                            evidence_level,
                            json.dumps(metadata) if metadata else None,
                        )
                    )
                    result = cur.fetchone()
                    if result:
                        ids.append(result[0])

                conn.commit()

        return ids

    @timed("guidelines_vector_search")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        filter_specialties: Optional[list[str]] = None,
        filter_sources: Optional[list[str]] = None,
        filter_recommendation_class: Optional[str] = None,
        filter_evidence_level: Optional[str] = None,
        ef_search: Optional[int] = None,
    ) -> list[GuidelineSearchResult]:
        """Search for similar guideline embeddings using cosine similarity.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            filter_specialties: Filter by guideline specialties
            filter_sources: Filter by source organizations
            filter_recommendation_class: Filter by recommendation class
            filter_evidence_level: Filter by evidence level
            ef_search: HNSW ef_search parameter for quality/speed tradeoff

        Returns:
            List of GuidelineSearchResult objects with similarity scores
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            self._ensure_pgvector(conn)

            with conn.cursor() as cur:
                # Set HNSW ef_search parameter
                ef_search_val = ef_search or DEFAULT_HNSW_EF_SEARCH
                cur.execute(f"SET hnsw.ef_search = {ef_search_val}")

                # Convert embedding to string format
                embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

                # Build query with joins to guidelines table for metadata
                query = """
                    SELECT
                        ge.guideline_id,
                        ge.chunk_index,
                        ge.chunk_text,
                        1 - (ge.embedding <=> %s::vector) as similarity,
                        ge.section_type,
                        ge.recommendation_class,
                        ge.evidence_level,
                        g.title as guideline_title,
                        g.source as guideline_source,
                        g.version as guideline_version,
                        g.specialty,
                        g.effective_date,
                        ge.metadata
                    FROM guideline_embeddings ge
                    LEFT JOIN guidelines g ON g.id = ge.guideline_id
                    WHERE 1=1
                """
                params = [embedding_str]

                # Apply filters
                if filter_specialties:
                    placeholders = ",".join(["%s"] * len(filter_specialties))
                    query += f" AND g.specialty IN ({placeholders})"
                    params.extend(filter_specialties)

                if filter_sources:
                    placeholders = ",".join(["%s"] * len(filter_sources))
                    query += f" AND g.source IN ({placeholders})"
                    params.extend(filter_sources)

                if filter_recommendation_class:
                    query += " AND ge.recommendation_class = %s"
                    params.append(filter_recommendation_class)

                if filter_evidence_level:
                    query += " AND ge.evidence_level = %s"
                    params.append(filter_evidence_level)

                if similarity_threshold > 0:
                    query += " AND 1 - (ge.embedding <=> %s::vector) >= %s"
                    params.extend([embedding_str, similarity_threshold])

                query += " ORDER BY ge.embedding <=> %s::vector LIMIT %s"
                params.extend([embedding_str, top_k])

                cur.execute(query, params)
                rows = cur.fetchall()

        results = []
        for row in rows:
            (guideline_id, chunk_idx, chunk_text, similarity, section_type,
             rec_class, evidence_level, title, source, version,
             specialty, effective_date, metadata_val) = row

            # Handle metadata
            if metadata_val is None:
                metadata = None
            elif isinstance(metadata_val, dict):
                metadata = metadata_val
            else:
                metadata = json.loads(metadata_val)

            results.append(GuidelineSearchResult(
                guideline_id=str(guideline_id),
                chunk_index=chunk_idx,
                chunk_text=chunk_text,
                similarity_score=float(similarity),
                section_type=section_type or "recommendation",
                recommendation_class=rec_class,
                evidence_level=evidence_level,
                guideline_title=title,
                guideline_source=source,
                guideline_version=version,
                specialty=specialty,
                effective_date=str(effective_date) if effective_date else None,
                metadata=metadata,
            ))

        return results

    @timed("guidelines_bm25_search")
    def search_bm25(
        self,
        query: str,
        top_k: int = 10,
        filter_specialties: Optional[list[str]] = None,
        filter_sources: Optional[list[str]] = None,
    ) -> list[GuidelineSearchResult]:
        """Perform BM25 full-text search on guidelines.

        Args:
            query: Search query text
            top_k: Number of results to return
            filter_specialties: Filter by guideline specialties
            filter_sources: Filter by source organizations

        Returns:
            List of GuidelineSearchResult objects with BM25 scores
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Check if search_vector column exists
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'guideline_embeddings'
                    AND column_name = 'search_vector'
                """)
                if not cur.fetchone():
                    logger.warning("search_vector column not found in guideline_embeddings")
                    return []

                # Build query
                sql = """
                    SELECT
                        ge.guideline_id,
                        ge.chunk_index,
                        ge.chunk_text,
                        ts_rank_cd(ge.search_vector, plainto_tsquery('english', %s)) as rank,
                        ge.section_type,
                        ge.recommendation_class,
                        ge.evidence_level,
                        g.title as guideline_title,
                        g.source as guideline_source,
                        g.version as guideline_version,
                        g.specialty,
                        g.effective_date,
                        ge.metadata
                    FROM guideline_embeddings ge
                    LEFT JOIN guidelines g ON g.id = ge.guideline_id
                    WHERE ge.search_vector @@ plainto_tsquery('english', %s)
                """
                params = [query, query]

                if filter_specialties:
                    placeholders = ",".join(["%s"] * len(filter_specialties))
                    sql += f" AND g.specialty IN ({placeholders})"
                    params.extend(filter_specialties)

                if filter_sources:
                    placeholders = ",".join(["%s"] * len(filter_sources))
                    sql += f" AND g.source IN ({placeholders})"
                    params.extend(filter_sources)

                sql += " ORDER BY rank DESC LIMIT %s"
                params.append(top_k)

                cur.execute(sql, params)
                rows = cur.fetchall()

        results = []
        for row in rows:
            (guideline_id, chunk_idx, chunk_text, rank, section_type,
             rec_class, evidence_level, title, source, version,
             specialty, effective_date, metadata_val) = row

            if metadata_val is None:
                metadata = None
            elif isinstance(metadata_val, dict):
                metadata = metadata_val
            else:
                metadata = json.loads(metadata_val)

            # Normalize rank to 0-1 range
            normalized_score = min(1.0, float(rank) * 10)

            results.append(GuidelineSearchResult(
                guideline_id=str(guideline_id),
                chunk_index=chunk_idx,
                chunk_text=chunk_text,
                similarity_score=normalized_score,
                section_type=section_type or "recommendation",
                recommendation_class=rec_class,
                evidence_level=evidence_level,
                guideline_title=title,
                guideline_source=source,
                guideline_version=version,
                specialty=specialty,
                effective_date=str(effective_date) if effective_date else None,
                metadata=metadata,
            ))

        return results

    def list_guidelines(self) -> list:
        """List all guidelines from the remote guidelines table.

        Returns:
            List of GuidelineListItem objects from the guidelines table
        """
        from src.rag.guidelines_models import GuidelineListItem, GuidelineUploadStatus

        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        g.id,
                        g.filename,
                        g.title,
                        g.specialty,
                        g.source,
                        g.version,
                        g.effective_date,
                        g.document_type,
                        g.upload_status,
                        g.neon_synced,
                        g.neo4j_synced,
                        g.created_at,
                        COUNT(ge.id) as chunk_count
                    FROM guidelines g
                    LEFT JOIN guideline_embeddings ge ON ge.guideline_id = g.id
                    GROUP BY g.id, g.filename, g.title, g.specialty, g.source,
                             g.version, g.effective_date, g.document_type,
                             g.upload_status, g.neon_synced, g.neo4j_synced,
                             g.created_at
                    ORDER BY g.created_at DESC
                """)
                rows = cur.fetchall()

        results = []
        for row in rows:
            (gid, filename, title, specialty, source, version,
             effective_date, document_type, upload_status,
             neon_synced, neo4j_synced, created_at, chunk_count) = row

            try:
                status = GuidelineUploadStatus(upload_status) if upload_status else GuidelineUploadStatus.COMPLETED
            except (ValueError, KeyError):
                status = GuidelineUploadStatus.COMPLETED

            from datetime import datetime
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    created_at = datetime.now()
            elif created_at is None:
                created_at = datetime.now()

            results.append(GuidelineListItem(
                guideline_id=str(gid),
                filename=filename or "Unknown",
                title=title,
                specialty=specialty or "general",
                source=source or "OTHER",
                version=version,
                effective_date=str(effective_date) if effective_date else None,
                document_type=document_type or "treatment_protocol",
                chunk_count=chunk_count or 0,
                upload_status=status,
                neon_synced=bool(neon_synced) if neon_synced is not None else True,
                neo4j_synced=bool(neo4j_synced) if neo4j_synced is not None else False,
                created_at=created_at,
            ))

        return results

    def delete_guideline_complete(self, guideline_id: str) -> bool:
        """Delete a guideline completely from both guidelines and guideline_embeddings tables.

        Args:
            guideline_id: UUID of the guideline to delete

        Returns:
            True if successfully deleted
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Delete embeddings first (foreign key)
                cur.execute(
                    "DELETE FROM guideline_embeddings WHERE guideline_id = %s::uuid",
                    (guideline_id,)
                )
                embeddings_deleted = cur.rowcount

                # Delete the guideline record
                cur.execute(
                    "DELETE FROM guidelines WHERE id = %s::uuid",
                    (guideline_id,)
                )
                guideline_deleted = cur.rowcount

                conn.commit()

        logger.info(
            f"Deleted guideline {guideline_id}: "
            f"{guideline_deleted} record(s), {embeddings_deleted} embedding(s)"
        )
        return guideline_deleted > 0

    def delete_guideline(self, guideline_id: str) -> int:
        """Delete all embeddings for a guideline.

        Args:
            guideline_id: UUID of the guideline

        Returns:
            Number of rows deleted
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM guideline_embeddings WHERE guideline_id = %s::uuid",
                    (guideline_id,)
                )
                deleted = cur.rowcount
                conn.commit()

        logger.info(f"Deleted {deleted} embeddings for guideline {guideline_id}")
        return deleted

    def get_guideline_chunks(self, guideline_id: str) -> list[dict]:
        """Get all chunks for a guideline.

        Args:
            guideline_id: UUID of the guideline

        Returns:
            List of chunk info dicts
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, chunk_index, chunk_text, section_type,
                           recommendation_class, evidence_level, metadata, created_at
                    FROM guideline_embeddings
                    WHERE guideline_id = %s::uuid
                    ORDER BY chunk_index
                    """,
                    (guideline_id,)
                )
                rows = cur.fetchall()

        results = []
        for row in rows:
            metadata_val = row[6]
            if metadata_val is None:
                metadata = None
            elif isinstance(metadata_val, dict):
                metadata = metadata_val
            else:
                metadata = json.loads(metadata_val)

            results.append({
                "id": row[0],
                "chunk_index": row[1],
                "chunk_text": row[2],
                "section_type": row[3],
                "recommendation_class": row[4],
                "evidence_level": row[5],
                "metadata": metadata,
                "created_at": row[7],
            })
        return results

    def get_stats(self) -> dict:
        """Get guidelines vector store statistics.

        Returns:
            Dict with stats
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Total embeddings
                cur.execute("SELECT COUNT(*) FROM guideline_embeddings")
                total_embeddings = cur.fetchone()[0]

                # Unique guidelines
                cur.execute("SELECT COUNT(DISTINCT guideline_id) FROM guideline_embeddings")
                total_guidelines = cur.fetchone()[0]

                # By specialty
                cur.execute("""
                    SELECT g.specialty, COUNT(DISTINCT g.id)
                    FROM guidelines g
                    GROUP BY g.specialty
                """)
                by_specialty = {row[0]: row[1] for row in cur.fetchall()}

                # By source
                cur.execute("""
                    SELECT g.source, COUNT(DISTINCT g.id)
                    FROM guidelines g
                    GROUP BY g.source
                """)
                by_source = {row[0]: row[1] for row in cur.fetchall()}

        return {
            "total_embeddings": total_embeddings,
            "total_guidelines": total_guidelines,
            "by_specialty": by_specialty,
            "by_source": by_source,
        }

    def health_check(self) -> bool:
        """Check if the guidelines vector store is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            pool = self._get_pool()
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return cur.fetchone()[0] == 1
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Guidelines vector store health check failed ({error_type}): {e}")
            return False

    def close(self):
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            self._pool = None


# Singleton instance
_guidelines_store: Optional[GuidelinesVectorStore] = None


def get_guidelines_vector_store() -> GuidelinesVectorStore:
    """Get the global guidelines vector store instance.

    Returns:
        GuidelinesVectorStore instance
    """
    global _guidelines_store
    if _guidelines_store is None:
        _guidelines_store = GuidelinesVectorStore()
    return _guidelines_store


def reset_guidelines_vector_store():
    """Reset the global guidelines vector store instance."""
    global _guidelines_store
    if _guidelines_store:
        _guidelines_store.close()
        _guidelines_store = None
