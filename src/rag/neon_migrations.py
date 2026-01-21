"""
Neon PostgreSQL migrations for RAG system.

Handles schema migrations for the Neon vector store,
specifically for search quality improvements.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


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

    def check_migration_status(self) -> dict:
        """Check the status of all migrations.

        Returns:
            Dictionary with migration status
        """
        status = {
            "search_vector_column": False,
            "search_vector_index": False,
            "search_vector_trigger": False,
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

                    # Check index exists
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
