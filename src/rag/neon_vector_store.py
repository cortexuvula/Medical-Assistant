"""
Neon PostgreSQL vector store for RAG system.

Handles pgvector operations for document embeddings:
- Upsert embeddings
- Vector similarity search (with HNSW index support)
- Document management

Performance optimizations:
- HNSW index for approximate nearest neighbor search (10-50x faster)
- Cosine similarity for semantic search
- Configurable ef_search parameter for quality/speed tradeoff
"""

import json
import os
import pathlib
from typing import Any, Optional

from dotenv import load_dotenv
from utils.structured_logging import get_logger, timed

from rag.models import VectorSearchQuery, VectorSearchResult
from rag.exceptions import (
    VectorSearchError,
    RAGConnectionError,
    RAGConfigurationError,
    RAGErrorCodes,
)

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

logger = get_logger(__name__)

# Default HNSW search parameter
# Higher values = better recall but slower search
# Typical values: 40 (fast), 100 (balanced), 200+ (high recall)
DEFAULT_HNSW_EF_SEARCH = 40


class NeonVectorStore:
    """Vector store using Neon PostgreSQL with pgvector."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        pool_size: int = 5,
    ):
        """Initialize Neon vector store.

        Args:
            connection_string: PostgreSQL connection string
            pool_size: Connection pool size
        """
        self._connection_string = connection_string
        self._pool_size = pool_size
        self._pool = None

    def _get_connection_string(self) -> str:
        """Get connection string from config or environment."""
        if self._connection_string:
            return self._connection_string

        # Try environment variable
        conn_str = os.environ.get("NEON_DATABASE_URL")
        if conn_str:
            return conn_str

        # Try settings
        try:
            from settings.settings import SETTINGS
            conn_str = SETTINGS.get("neon_database_url")
            if conn_str:
                return conn_str
        except Exception:
            pass

        raise ValueError(
            "Neon connection string not found. "
            "Set NEON_DATABASE_URL environment variable or configure in settings."
        )

    def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                # Import psycopg first to ensure base package loads
                import psycopg
                logger.debug(f"psycopg loaded from: {psycopg.__file__}")
            except ImportError as e:
                logger.error(f"Failed to import psycopg: {e}")
                raise ImportError(
                    "psycopg is required for Neon vector store. "
                    f"Install with: pip install 'psycopg[binary]'. Error: {e}"
                )

            try:
                import psycopg_pool
            except ImportError as e:
                logger.error(f"Failed to import psycopg_pool: {e}")
                raise ImportError(
                    "psycopg_pool is required for Neon vector store. "
                    f"Install with: pip install 'psycopg[binary]'. Error: {e}"
                )

            conn_str = self._get_connection_string()
            self._pool = psycopg_pool.ConnectionPool(
                conn_str,
                min_size=1,
                max_size=self._pool_size,
                open=True,
            )

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
        document_id: str,
        chunk_index: int,
        chunk_text: str,
        embedding: list[float],
        metadata: Optional[dict] = None,
    ) -> int:
        """Upsert a single embedding.

        Args:
            document_id: UUID of the document
            chunk_index: Index of the chunk within the document
            chunk_text: Text content of the chunk
            embedding: Embedding vector
            metadata: Optional metadata dict

        Returns:
            ID of the inserted/updated row
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            self._ensure_pgvector(conn)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_embeddings
                    (document_id, chunk_index, chunk_text, embedding, metadata)
                    VALUES (%s::uuid, %s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_index)
                    DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        created_at = NOW()
                    RETURNING id
                    """,
                    (
                        document_id,
                        chunk_index,
                        chunk_text,
                        embedding,
                        json.dumps(metadata) if metadata else None,
                    )
                )
                result = cur.fetchone()
                conn.commit()
                return result[0] if result else None

    def upsert_embeddings_batch(
        self,
        document_id: str,
        chunks: list[tuple[int, str, list[float], Optional[dict]]],
    ) -> list[int]:
        """Upsert multiple embeddings for a document.

        Args:
            document_id: UUID of the document
            chunks: List of (chunk_index, chunk_text, embedding, metadata) tuples

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
                # Use executemany for batch insert
                for chunk_index, chunk_text, embedding, metadata in chunks:
                    cur.execute(
                        """
                        INSERT INTO document_embeddings
                        (document_id, chunk_index, chunk_text, embedding, metadata)
                        VALUES (%s::uuid, %s, %s, %s, %s)
                        ON CONFLICT (document_id, chunk_index)
                        DO UPDATE SET
                            chunk_text = EXCLUDED.chunk_text,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            created_at = NOW()
                        RETURNING id
                        """,
                        (
                            document_id,
                            chunk_index,
                            chunk_text,
                            embedding,
                            json.dumps(metadata) if metadata else None,
                        )
                    )
                    result = cur.fetchone()
                    if result:
                        ids.append(result[0])

                conn.commit()

        return ids

    @timed("rag_vector_search")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        filter_document_ids: Optional[list[str]] = None,
        ef_search: Optional[int] = None,
    ) -> list[VectorSearchResult]:
        """Search for similar embeddings using cosine similarity.

        When an HNSW index exists, this uses approximate nearest neighbor
        search for significantly faster queries (10-50x improvement).

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1 for cosine)
            filter_document_ids: Optional list of document IDs to filter
            ef_search: HNSW ef_search parameter for quality/speed tradeoff.
                      Higher values = better recall but slower.
                      Default: 40. Typical values: 40 (fast), 100 (balanced), 200+ (high recall)

        Returns:
            List of VectorSearchResult objects with cosine similarity scores
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            self._ensure_pgvector(conn)

            with conn.cursor() as cur:
                # Set HNSW ef_search parameter for this session
                # This controls the trade-off between search quality and speed
                ef_search_val = ef_search or DEFAULT_HNSW_EF_SEARCH
                cur.execute(f"SET hnsw.ef_search = {ef_search_val}")

                # Convert embedding to string format for vector cast
                embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

                # Build query using cosine distance operator (<=>)
                # Cosine similarity = 1 - cosine_distance
                # The <=> operator uses HNSW index when available
                query = """
                    SELECT
                        document_id,
                        chunk_index,
                        chunk_text,
                        1 - (embedding <=> %s::vector) as similarity,
                        metadata
                    FROM document_embeddings
                    WHERE 1=1
                """
                params = [embedding_str]

                if filter_document_ids:
                    placeholders = ",".join(["%s::uuid"] * len(filter_document_ids))
                    query += f" AND document_id IN ({placeholders})"
                    params.extend(filter_document_ids)

                if similarity_threshold > 0:
                    query += " AND 1 - (embedding <=> %s::vector) >= %s"
                    params.extend([embedding_str, similarity_threshold])

                query += " ORDER BY embedding <=> %s::vector LIMIT %s"
                params.extend([embedding_str, top_k])

                cur.execute(query, params)
                rows = cur.fetchall()

        results = []
        for row in rows:
            doc_id, chunk_idx, chunk_text, similarity, metadata_val = row
            # Handle metadata - psycopg may return dict directly for JSONB
            if metadata_val is None:
                metadata = None
            elif isinstance(metadata_val, dict):
                metadata = metadata_val
            else:
                metadata = json.loads(metadata_val)

            results.append(VectorSearchResult(
                document_id=str(doc_id),
                chunk_index=chunk_idx,
                chunk_text=chunk_text,
                similarity_score=float(similarity),
                metadata=metadata,
            ))

        return results

    def search_with_query(self, query: VectorSearchQuery) -> list[VectorSearchResult]:
        """Search using a VectorSearchQuery object.

        Args:
            query: VectorSearchQuery with search parameters

        Returns:
            List of VectorSearchResult objects
        """
        if not query.query_embedding:
            raise ValueError("query_embedding is required for search")

        return self.search(
            query_embedding=query.query_embedding,
            top_k=query.top_k,
            similarity_threshold=query.similarity_threshold,
            filter_document_ids=query.filter_document_ids,
        )

    def delete_document(self, document_id: str) -> int:
        """Delete all embeddings for a document.

        Args:
            document_id: UUID of the document

        Returns:
            Number of rows deleted
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM document_embeddings WHERE document_id = %s::uuid",
                    (document_id,)
                )
                deleted = cur.rowcount
                conn.commit()

        logger.info(f"Deleted {deleted} embeddings for document {document_id}")
        return deleted

    def delete_chunk(self, document_id: str, chunk_index: int) -> bool:
        """Delete a specific chunk.

        Args:
            document_id: UUID of the document
            chunk_index: Index of the chunk

        Returns:
            True if deleted, False if not found
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM document_embeddings
                    WHERE document_id = %s::uuid AND chunk_index = %s
                    """,
                    (document_id, chunk_index)
                )
                deleted = cur.rowcount > 0
                conn.commit()

        return deleted

    def get_document_chunks(self, document_id: str) -> list[dict]:
        """Get all chunks for a document.

        Args:
            document_id: UUID of the document

        Returns:
            List of chunk info dicts
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, chunk_index, chunk_text, metadata, created_at
                    FROM document_embeddings
                    WHERE document_id = %s::uuid
                    ORDER BY chunk_index
                    """,
                    (document_id,)
                )
                rows = cur.fetchall()

        results = []
        for row in rows:
            metadata_val = row[3]
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
                "metadata": metadata,
                "created_at": row[4],
            })
        return results

    def get_stats(self) -> dict:
        """Get vector store statistics.

        Returns:
            Dict with stats
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Total embeddings
                cur.execute("SELECT COUNT(*) FROM document_embeddings")
                total_embeddings = cur.fetchone()[0]

                # Unique documents
                cur.execute("SELECT COUNT(DISTINCT document_id) FROM document_embeddings")
                total_documents = cur.fetchone()[0]

                # Average chunks per document
                cur.execute("""
                    SELECT AVG(chunk_count) FROM (
                        SELECT COUNT(*) as chunk_count
                        FROM document_embeddings
                        GROUP BY document_id
                    ) subq
                """)
                avg_chunks = cur.fetchone()[0] or 0

        return {
            "total_embeddings": total_embeddings,
            "total_documents": total_documents,
            "avg_chunks_per_document": round(float(avg_chunks), 1),
        }

    def health_check(self) -> bool:
        """Check if the vector store is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            pool = self._get_pool()
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return cur.fetchone()[0] == 1
        except RAGConnectionError:
            # Already logged, just return False
            return False
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Neon health check failed ({error_type}): {e}")
            return False

    @timed("rag_bm25_search")
    def search_bm25(
        self,
        query: str,
        top_k: int = 10,
        filter_document_ids: Optional[list[str]] = None,
    ) -> list[VectorSearchResult]:
        """Perform BM25 full-text search using PostgreSQL tsvector.

        Args:
            query: Search query text
            top_k: Number of results to return
            filter_document_ids: Optional list of document IDs to filter

        Returns:
            List of VectorSearchResult objects with BM25 scores
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Check if search_vector column exists
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'document_embeddings'
                    AND column_name = 'search_vector'
                """)
                if not cur.fetchone():
                    logger.warning("search_vector column not found, BM25 search unavailable")
                    return []

                # Build query
                sql = """
                    SELECT
                        document_id,
                        chunk_index,
                        chunk_text,
                        ts_rank_cd(search_vector, plainto_tsquery('english', %s)) as rank,
                        metadata
                    FROM document_embeddings
                    WHERE search_vector @@ plainto_tsquery('english', %s)
                """
                params = [query, query]

                if filter_document_ids:
                    placeholders = ",".join(["%s::uuid"] * len(filter_document_ids))
                    sql += f" AND document_id IN ({placeholders})"
                    params.extend(filter_document_ids)

                sql += " ORDER BY rank DESC LIMIT %s"
                params.append(top_k)

                cur.execute(sql, params)
                rows = cur.fetchall()

        results = []
        for row in rows:
            doc_id, chunk_idx, chunk_text, rank, metadata_val = row

            if metadata_val is None:
                metadata = None
            elif isinstance(metadata_val, dict):
                metadata = metadata_val
            else:
                metadata = json.loads(metadata_val)

            # Normalize rank to 0-1 range (ts_rank_cd typically < 1)
            normalized_score = min(1.0, float(rank) * 10)

            results.append(VectorSearchResult(
                document_id=str(doc_id),
                chunk_index=chunk_idx,
                chunk_text=chunk_text,
                similarity_score=normalized_score,  # Used as BM25 score
                metadata=metadata,
            ))

        return results

    def has_search_vector_column(self) -> bool:
        """Check if search_vector column exists for BM25 search.

        Returns:
            True if column exists, False otherwise
        """
        try:
            pool = self._get_pool()
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'document_embeddings'
                        AND column_name = 'search_vector'
                    """)
                    return cur.fetchone() is not None
        except RAGConnectionError:
            return False
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Failed to check search_vector column ({error_type}): {e}")
            return False

    def get_remote_document_summaries(self) -> list[dict]:
        """Get summaries of all documents stored in the remote Neon database.

        Queries document_embeddings for distinct document IDs and extracts
        metadata (filename, category, tags, chunk count) from the JSONB column.

        Returns:
            List of dicts with keys: document_id, filename, category, tags, chunk_count
        """
        pool = self._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Use DISTINCT ON to get one metadata sample per document_id
                # This avoids MIN() on JSONB which PostgreSQL doesn't support
                cur.execute("""
                    WITH doc_counts AS (
                        SELECT document_id, COUNT(*) as chunk_count
                        FROM document_embeddings
                        GROUP BY document_id
                    ),
                    sample_metadata AS (
                        SELECT DISTINCT ON (document_id)
                            document_id,
                            metadata
                        FROM document_embeddings
                        ORDER BY document_id, id
                    )
                    SELECT
                        dc.document_id,
                        dc.chunk_count,
                        sm.metadata as sample_metadata
                    FROM doc_counts dc
                    LEFT JOIN sample_metadata sm ON dc.document_id = sm.document_id
                """)
                rows = cur.fetchall()

        results = []
        for row in rows:
            doc_id, chunk_count, metadata_val = row

            # Parse metadata
            if metadata_val is None:
                metadata = {}
            elif isinstance(metadata_val, dict):
                metadata = metadata_val
            else:
                try:
                    metadata = json.loads(metadata_val)
                except Exception:
                    metadata = {}

            results.append({
                "document_id": str(doc_id),
                "filename": metadata.get("filename", "Unknown"),
                "category": metadata.get("category"),
                "tags": metadata.get("tags", []),
                "chunk_count": chunk_count,
            })

        return results

    def get_index_health(self) -> dict:
        """Get health and statistics for vector indexes.

        Returns:
            Dict with index health info including:
            - hnsw_index_exists: Whether HNSW index exists
            - hnsw_index_valid: Whether HNSW index is valid
            - hnsw_index_size_mb: Size of HNSW index in MB
            - search_vector_index_exists: Whether BM25 GIN index exists
            - total_embeddings: Total number of embeddings
            - pgvector_version: Version of pgvector extension
        """
        health = {
            "hnsw_index_exists": False,
            "hnsw_index_valid": False,
            "hnsw_index_size_mb": 0.0,
            "search_vector_index_exists": False,
            "total_embeddings": 0,
            "pgvector_version": None,
        }

        try:
            pool = self._get_pool()
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Check HNSW index
                    cur.execute("""
                        SELECT
                            pg_index.indisvalid,
                            pg_relation_size(c.oid) as size_bytes
                        FROM pg_indexes i
                        JOIN pg_class c ON c.relname = i.indexname
                        JOIN pg_index ON pg_index.indexrelid = c.oid
                        WHERE i.tablename = 'document_embeddings'
                        AND i.indexname = 'idx_document_embeddings_hnsw'
                    """)
                    hnsw_result = cur.fetchone()
                    if hnsw_result:
                        health["hnsw_index_exists"] = True
                        health["hnsw_index_valid"] = hnsw_result[0]
                        health["hnsw_index_size_mb"] = round(hnsw_result[1] / (1024 * 1024), 2)

                    # Check search_vector GIN index
                    cur.execute("""
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'document_embeddings'
                        AND indexname = 'idx_document_embeddings_search_vector'
                    """)
                    health["search_vector_index_exists"] = cur.fetchone() is not None

                    # Total embeddings count
                    cur.execute("SELECT COUNT(*) FROM document_embeddings")
                    health["total_embeddings"] = cur.fetchone()[0]

                    # pgvector version
                    cur.execute("""
                        SELECT extversion
                        FROM pg_extension
                        WHERE extname = 'vector'
                    """)
                    version_result = cur.fetchone()
                    if version_result:
                        health["pgvector_version"] = version_result[0]

        except RAGConnectionError:
            health["error"] = "Connection failed"
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Failed to get index health ({error_type}): {e}")
            health["error"] = str(e)

        return health

    def close(self):
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            self._pool = None


# Singleton instance
_vector_store: Optional[NeonVectorStore] = None


def get_vector_store() -> NeonVectorStore:
    """Get the global vector store instance.

    Returns:
        NeonVectorStore instance
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = NeonVectorStore()
    return _vector_store


def reset_vector_store():
    """Reset the global vector store instance."""
    global _vector_store
    if _vector_store:
        _vector_store.close()
        _vector_store = None
