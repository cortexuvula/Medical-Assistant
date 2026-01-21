"""
Neon PostgreSQL migrations for RAG system.

Handles schema migrations for the Neon vector store,
specifically for search quality improvements and performance optimization.

Includes:
- BM25 full-text search (search_vector column + GIN index)
- HNSW approximate nearest neighbor indexing (10-50x faster vector search)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# HNSW index configuration defaults
# These are optimized for 10K-100K documents
DEFAULT_HNSW_M = 16  # Number of bi-directional links
DEFAULT_HNSW_EF_CONSTRUCTION = 64  # Size of dynamic candidate list during build


class NeonMigrationManager:
    """Manages Neon PostgreSQL schema migrations."""

    def __init__(self, vector_store=None):
        """Initialize migration manager.

        Args:
            vector_store: NeonVectorStore instance
        """
        self._vector_store = vector_store

    def _get_vector_store(self):
        """Get or create vector store."""
        if self._vector_store is None:
            from rag.neon_vector_store import get_vector_store
            self._vector_store = get_vector_store()
        return self._vector_store

    def run_migrations(self) -> bool:
        """Run all pending Neon migrations.

        Returns:
            True if migrations ran successfully
        """
        try:
            # Run migrations in order
            self._migrate_add_search_vector()
            self._migrate_add_hnsw_index()
            logger.info("Neon migrations completed successfully")
            return True
        except Exception as e:
            logger.error(f"Neon migration failed: {e}")
            return False

    def _migrate_add_search_vector(self):
        """Add search_vector column and GIN index for BM25 search."""
        vector_store = self._get_vector_store()

        try:
            pool = vector_store._get_pool()

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Check if search_vector column already exists
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'document_embeddings'
                        AND column_name = 'search_vector'
                    """)

                    if cur.fetchone():
                        logger.info("search_vector column already exists")
                        return

                    logger.info("Adding search_vector column to document_embeddings")

                    # Add search_vector column
                    cur.execute("""
                        ALTER TABLE document_embeddings
                        ADD COLUMN IF NOT EXISTS search_vector tsvector
                    """)

                    # Populate search_vector from existing chunk_text
                    logger.info("Populating search_vector from existing data")
                    cur.execute("""
                        UPDATE document_embeddings
                        SET search_vector = to_tsvector('english', chunk_text)
                        WHERE search_vector IS NULL
                    """)

                    # Create GIN index for fast full-text search
                    logger.info("Creating GIN index for search_vector")
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_document_embeddings_search_vector
                        ON document_embeddings USING GIN(search_vector)
                    """)

                    # Create trigger to auto-update search_vector on insert/update
                    logger.info("Creating trigger for auto-updating search_vector")

                    # Create trigger function
                    cur.execute("""
                        CREATE OR REPLACE FUNCTION update_document_embeddings_search_vector()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            NEW.search_vector := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql
                    """)

                    # Create trigger
                    cur.execute("""
                        DROP TRIGGER IF EXISTS trg_update_search_vector ON document_embeddings
                    """)
                    cur.execute("""
                        CREATE TRIGGER trg_update_search_vector
                        BEFORE INSERT OR UPDATE OF chunk_text ON document_embeddings
                        FOR EACH ROW EXECUTE FUNCTION update_document_embeddings_search_vector()
                    """)

                    conn.commit()
                    logger.info("search_vector migration completed successfully")

        except Exception as e:
            logger.error(f"Failed to add search_vector column: {e}")
            raise

    def _migrate_add_hnsw_index(self):
        """Add HNSW index for fast approximate nearest neighbor search.

        HNSW (Hierarchical Navigable Small World) provides 10-50x faster
        vector similarity searches compared to sequential scan.

        Parameters:
            m=16: Number of bi-directional links per node (default 16)
            ef_construction=64: Size of dynamic candidate list during build
            vector_cosine_ops: Use cosine similarity for semantic search

        Note: Uses CREATE INDEX CONCURRENTLY for non-blocking index creation.
        """
        vector_store = self._get_vector_store()

        try:
            pool = vector_store._get_pool()

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Check if HNSW index already exists
                    cur.execute("""
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'document_embeddings'
                        AND indexname = 'idx_document_embeddings_hnsw'
                    """)

                    if cur.fetchone():
                        logger.info("HNSW index already exists")
                        return

                    # Check if pgvector extension supports HNSW
                    cur.execute("""
                        SELECT extversion
                        FROM pg_extension
                        WHERE extname = 'vector'
                    """)
                    result = cur.fetchone()
                    if not result:
                        logger.warning("pgvector extension not found, skipping HNSW index")
                        return

                    version = result[0]
                    logger.info(f"pgvector version: {version}")

                    # HNSW requires pgvector 0.5.0+
                    try:
                        major, minor = map(int, version.split('.')[:2])
                        if major == 0 and minor < 5:
                            logger.warning(f"pgvector {version} does not support HNSW (requires 0.5.0+)")
                            return
                    except ValueError:
                        logger.warning(f"Could not parse pgvector version: {version}")

                    logger.info("Creating HNSW index for document_embeddings (this may take a while)...")

                    # Commit current transaction before CONCURRENTLY
                    conn.commit()

                    # Create HNSW index with cosine similarity
                    # CONCURRENTLY allows reads/writes during index creation
                    # Note: CONCURRENTLY cannot be in a transaction block
                    conn.autocommit = True
                    try:
                        cur.execute(f"""
                            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_embeddings_hnsw
                            ON document_embeddings
                            USING hnsw (embedding vector_cosine_ops)
                            WITH (m = {DEFAULT_HNSW_M}, ef_construction = {DEFAULT_HNSW_EF_CONSTRUCTION})
                        """)
                    finally:
                        conn.autocommit = False

                    logger.info("HNSW index created successfully")

        except Exception as e:
            logger.error(f"Failed to create HNSW index: {e}")
            # Don't raise - HNSW is an optimization, not required
            logger.warning("Vector search will continue using sequential scan")

    def check_migration_status(self) -> dict:
        """Check the status of all migrations.

        Returns:
            Dictionary with migration status
        """
        status = {
            "search_vector_column": False,
            "search_vector_index": False,
            "search_vector_trigger": False,
            "hnsw_index": False,
            "hnsw_index_valid": False,
            "pgvector_version": None,
        }

        try:
            vector_store = self._get_vector_store()
            pool = vector_store._get_pool()

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Check column exists
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'document_embeddings'
                        AND column_name = 'search_vector'
                    """)
                    status["search_vector_column"] = cur.fetchone() is not None

                    # Check search_vector index exists
                    cur.execute("""
                        SELECT indexname
                        FROM pg_indexes
                        WHERE tablename = 'document_embeddings'
                        AND indexname = 'idx_document_embeddings_search_vector'
                    """)
                    status["search_vector_index"] = cur.fetchone() is not None

                    # Check trigger exists
                    cur.execute("""
                        SELECT tgname
                        FROM pg_trigger
                        WHERE tgname = 'trg_update_search_vector'
                    """)
                    status["search_vector_trigger"] = cur.fetchone() is not None

                    # Check HNSW index exists and is valid
                    cur.execute("""
                        SELECT i.indexname, pg_index.indisvalid
                        FROM pg_indexes i
                        JOIN pg_class c ON c.relname = i.indexname
                        JOIN pg_index ON pg_index.indexrelid = c.oid
                        WHERE i.tablename = 'document_embeddings'
                        AND i.indexname = 'idx_document_embeddings_hnsw'
                    """)
                    hnsw_result = cur.fetchone()
                    if hnsw_result:
                        status["hnsw_index"] = True
                        status["hnsw_index_valid"] = hnsw_result[1]

                    # Check pgvector version
                    cur.execute("""
                        SELECT extversion
                        FROM pg_extension
                        WHERE extname = 'vector'
                    """)
                    version_result = cur.fetchone()
                    if version_result:
                        status["pgvector_version"] = version_result[0]

        except Exception as e:
            logger.warning(f"Failed to check migration status: {e}")

        return status

    def get_search_vector_stats(self) -> dict:
        """Get statistics about search_vector population.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_rows": 0,
            "rows_with_search_vector": 0,
            "rows_without_search_vector": 0,
        }

        try:
            vector_store = self._get_vector_store()
            pool = vector_store._get_pool()

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Total rows
                    cur.execute("SELECT COUNT(*) FROM document_embeddings")
                    stats["total_rows"] = cur.fetchone()[0]

                    # Rows with search_vector
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM document_embeddings
                        WHERE search_vector IS NOT NULL
                    """)
                    stats["rows_with_search_vector"] = cur.fetchone()[0]

                    stats["rows_without_search_vector"] = (
                        stats["total_rows"] - stats["rows_with_search_vector"]
                    )

        except Exception as e:
            logger.warning(f"Failed to get search_vector stats: {e}")

        return stats

    def get_hnsw_index_health(self) -> dict:
        """Get health and statistics for the HNSW index.

        Returns:
            Dictionary with HNSW index health info:
            - exists: Whether index exists
            - is_valid: Whether index is valid (not invalidated by concurrent ops)
            - size_bytes: Approximate size of the index
            - size_mb: Size in megabytes
            - index_type: Type of index (should be 'hnsw')
            - m: HNSW m parameter (bi-directional links)
            - ef_construction: HNSW ef_construction parameter
        """
        health = {
            "exists": False,
            "is_valid": False,
            "size_bytes": 0,
            "size_mb": 0.0,
            "index_type": None,
            "m": None,
            "ef_construction": None,
        }

        try:
            vector_store = self._get_vector_store()
            pool = vector_store._get_pool()

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # Check if index exists and get validity
                    cur.execute("""
                        SELECT
                            pg_index.indisvalid,
                            pg_relation_size(c.oid) as size_bytes,
                            am.amname as index_type
                        FROM pg_indexes i
                        JOIN pg_class c ON c.relname = i.indexname
                        JOIN pg_index ON pg_index.indexrelid = c.oid
                        JOIN pg_am am ON c.relam = am.oid
                        WHERE i.tablename = 'document_embeddings'
                        AND i.indexname = 'idx_document_embeddings_hnsw'
                    """)
                    result = cur.fetchone()

                    if result:
                        health["exists"] = True
                        health["is_valid"] = result[0]
                        health["size_bytes"] = result[1]
                        health["size_mb"] = round(result[1] / (1024 * 1024), 2)
                        health["index_type"] = result[2]

                        # Get HNSW-specific options from index definition
                        cur.execute("""
                            SELECT indexdef
                            FROM pg_indexes
                            WHERE tablename = 'document_embeddings'
                            AND indexname = 'idx_document_embeddings_hnsw'
                        """)
                        def_result = cur.fetchone()
                        if def_result:
                            indexdef = def_result[0]
                            # Parse m and ef_construction from definition
                            import re
                            m_match = re.search(r'm\s*=\s*(\d+)', indexdef)
                            ef_match = re.search(r'ef_construction\s*=\s*(\d+)', indexdef)
                            if m_match:
                                health["m"] = int(m_match.group(1))
                            if ef_match:
                                health["ef_construction"] = int(ef_match.group(1))

        except Exception as e:
            logger.warning(f"Failed to get HNSW index health: {e}")

        return health


# Singleton instance
_migration_manager: Optional[NeonMigrationManager] = None


def get_neon_migration_manager() -> NeonMigrationManager:
    """Get the global Neon migration manager instance.

    Returns:
        NeonMigrationManager instance
    """
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = NeonMigrationManager()
    return _migration_manager


def run_neon_migrations() -> bool:
    """Run all pending Neon migrations.

    Returns:
        True if successful
    """
    manager = get_neon_migration_manager()
    return manager.run_migrations()


def check_neon_migration_status() -> dict:
    """Check status of Neon migrations.

    Returns:
        Dictionary with migration status
    """
    manager = get_neon_migration_manager()
    return manager.check_migration_status()
