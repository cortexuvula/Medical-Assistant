"""
Clinical Guidelines Database Migrations for Neon PostgreSQL.

Creates and manages the database schema for the clinical guidelines system.
This runs against the SEPARATE guidelines database (CLINICAL_GUIDELINES_DATABASE_URL).

Tables:
    - guidelines: Metadata for clinical guideline documents
    - guideline_embeddings: Vector embeddings for guideline chunks

Indexes:
    - HNSW index on guideline_embeddings.embedding for fast vector search
    - GIN index on search_vector for BM25 full-text search
"""

import logging
import os
import pathlib
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
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
    load_dotenv()

_load_env()

logger = logging.getLogger(__name__)


# Migration versions
CURRENT_VERSION = 1

# SQL migrations by version
MIGRATIONS = {
    1: """
    -- Enable pgvector extension if not already enabled
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Create guidelines table (metadata for guideline documents)
    CREATE TABLE IF NOT EXISTS guidelines (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        title TEXT,
        filename TEXT NOT NULL,
        file_type VARCHAR(10),
        file_path TEXT,
        file_size_bytes INTEGER DEFAULT 0,
        page_count INTEGER DEFAULT 0,

        -- Guideline-specific metadata
        specialty VARCHAR(50),
        source VARCHAR(50),
        version VARCHAR(20),
        effective_date DATE,
        expiration_date DATE,
        document_type VARCHAR(50),

        -- Arrays for searchable metadata
        authors TEXT[] DEFAULT '{}',
        keywords TEXT[] DEFAULT '{}',
        conditions_covered TEXT[] DEFAULT '{}',
        medications_covered TEXT[] DEFAULT '{}',

        -- Processing status
        upload_status VARCHAR(20) DEFAULT 'pending',
        chunk_count INTEGER DEFAULT 0,
        neon_synced BOOLEAN DEFAULT FALSE,
        neo4j_synced BOOLEAN DEFAULT FALSE,
        error_message TEXT,

        -- Additional metadata as JSONB
        metadata JSONB DEFAULT '{}',

        -- Timestamps
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Create guideline_embeddings table (chunks with vectors)
    CREATE TABLE IF NOT EXISTS guideline_embeddings (
        id SERIAL PRIMARY KEY,
        guideline_id UUID NOT NULL REFERENCES guidelines(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        chunk_text TEXT NOT NULL,

        -- Guideline-specific metadata for each chunk
        section_type VARCHAR(30) DEFAULT 'recommendation',
        recommendation_class VARCHAR(10),
        evidence_level VARCHAR(10),

        -- Vector embedding (1536 dimensions for OpenAI embeddings)
        embedding vector(1536),

        -- Full-text search vector for BM25
        search_vector tsvector GENERATED ALWAYS AS (
            to_tsvector('english', chunk_text)
        ) STORED,

        -- Additional metadata
        metadata JSONB DEFAULT '{}',

        -- Timestamps
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),

        -- Ensure unique chunks per guideline
        UNIQUE (guideline_id, chunk_index)
    );

    -- Create indexes

    -- HNSW index for fast approximate nearest neighbor search
    CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_hnsw
    ON guideline_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

    -- GIN index for full-text search (BM25)
    CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_search_vector
    ON guideline_embeddings
    USING GIN (search_vector);

    -- Index for filtering by guideline
    CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_guideline_id
    ON guideline_embeddings (guideline_id);

    -- Index for filtering by section type
    CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_section_type
    ON guideline_embeddings (section_type);

    -- Index for filtering by recommendation class
    CREATE INDEX IF NOT EXISTS idx_guideline_embeddings_rec_class
    ON guideline_embeddings (recommendation_class)
    WHERE recommendation_class IS NOT NULL;

    -- Indexes on guidelines table for filtering
    CREATE INDEX IF NOT EXISTS idx_guidelines_specialty
    ON guidelines (specialty);

    CREATE INDEX IF NOT EXISTS idx_guidelines_source
    ON guidelines (source);

    CREATE INDEX IF NOT EXISTS idx_guidelines_effective_date
    ON guidelines (effective_date);

    CREATE INDEX IF NOT EXISTS idx_guidelines_upload_status
    ON guidelines (upload_status);

    -- GIN index for array searches
    CREATE INDEX IF NOT EXISTS idx_guidelines_conditions
    ON guidelines USING GIN (conditions_covered);

    CREATE INDEX IF NOT EXISTS idx_guidelines_medications
    ON guidelines USING GIN (medications_covered);

    -- Create migrations tracking table
    CREATE TABLE IF NOT EXISTS guideline_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMPTZ DEFAULT NOW(),
        description TEXT
    );

    -- Record this migration
    INSERT INTO guideline_migrations (version, description)
    VALUES (1, 'Initial clinical guidelines schema')
    ON CONFLICT (version) DO NOTHING;
    """,
}


def get_connection_string() -> Optional[str]:
    """Get the clinical guidelines database connection string.

    Uses CLINICAL_GUIDELINES_DATABASE_URL, NOT the main NEON_DATABASE_URL.
    """
    conn_str = os.environ.get("CLINICAL_GUIDELINES_DATABASE_URL")
    if conn_str:
        return conn_str

    try:
        from src.settings.settings import SETTINGS
        guidelines_settings = SETTINGS.get("clinical_guidelines", {})
        return guidelines_settings.get("database_url")
    except Exception:
        pass

    return None


def get_current_version(cursor) -> int:
    """Get the current migration version from the database."""
    try:
        cursor.execute("""
            SELECT version FROM guideline_migrations
            ORDER BY version DESC LIMIT 1
        """)
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception:
        # Table doesn't exist yet
        return 0


def run_guidelines_migrations(
    connection_string: Optional[str] = None,
    target_version: Optional[int] = None,
) -> bool:
    """Run database migrations for the clinical guidelines system.

    Args:
        connection_string: PostgreSQL connection string (optional, uses env if not provided)
        target_version: Target version to migrate to (optional, uses latest if not provided)

    Returns:
        True if migrations were successful, False otherwise
    """
    conn_str = connection_string or get_connection_string()
    if not conn_str:
        logger.error(
            "Clinical Guidelines database connection string not found. "
            "Set CLINICAL_GUIDELINES_DATABASE_URL environment variable."
        )
        return False

    try:
        import psycopg
    except ImportError:
        logger.error("psycopg is required for migrations. Install with: pip install 'psycopg[binary]'")
        return False

    target = target_version or CURRENT_VERSION

    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                current = get_current_version(cur)

                if current >= target:
                    logger.info(f"Guidelines database already at version {current}, no migrations needed")
                    return True

                logger.info(f"Migrating guidelines database from version {current} to {target}")

                # Run each migration in order
                for version in range(current + 1, target + 1):
                    if version not in MIGRATIONS:
                        logger.error(f"Migration version {version} not found")
                        return False

                    logger.info(f"Applying migration version {version}...")
                    cur.execute(MIGRATIONS[version])

                conn.commit()
                logger.info(f"Successfully migrated guidelines database to version {target}")
                return True

    except Exception as e:
        logger.error(f"Guidelines migration failed: {e}")
        return False


def check_guidelines_schema() -> dict:
    """Check the current state of the guidelines database schema.

    Returns:
        Dict with schema status information
    """
    conn_str = get_connection_string()
    if not conn_str:
        return {"error": "Connection string not found", "configured": False}

    try:
        import psycopg
    except ImportError:
        return {"error": "psycopg not installed", "configured": False}

    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                status = {
                    "configured": True,
                    "connected": True,
                    "current_version": get_current_version(cur),
                    "latest_version": CURRENT_VERSION,
                    "tables": {},
                    "indexes": {},
                }

                # Check tables
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('guidelines', 'guideline_embeddings', 'guideline_migrations')
                """)
                status["tables"] = {row[0]: True for row in cur.fetchall()}

                # Check for pgvector extension
                cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                status["pgvector_enabled"] = cur.fetchone() is not None

                # Check indexes
                cur.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename IN ('guidelines', 'guideline_embeddings')
                """)
                status["indexes"] = {row[0]: True for row in cur.fetchall()}

                # Count records
                if "guidelines" in status["tables"]:
                    cur.execute("SELECT COUNT(*) FROM guidelines")
                    status["guideline_count"] = cur.fetchone()[0]

                if "guideline_embeddings" in status["tables"]:
                    cur.execute("SELECT COUNT(*) FROM guideline_embeddings")
                    status["embedding_count"] = cur.fetchone()[0]

                return status

    except Exception as e:
        return {"error": str(e), "configured": True, "connected": False}


def reset_guidelines_database(
    connection_string: Optional[str] = None,
    confirm: bool = False,
) -> bool:
    """Reset the guidelines database by dropping all tables.

    WARNING: This will delete all guideline data!

    Args:
        connection_string: PostgreSQL connection string
        confirm: Must be True to proceed with reset

    Returns:
        True if reset was successful
    """
    if not confirm:
        logger.error("Reset requires confirm=True to proceed")
        return False

    conn_str = connection_string or get_connection_string()
    if not conn_str:
        logger.error("Connection string not found")
        return False

    try:
        import psycopg

        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                logger.warning("Dropping all guidelines tables...")
                cur.execute("DROP TABLE IF EXISTS guideline_embeddings CASCADE")
                cur.execute("DROP TABLE IF EXISTS guidelines CASCADE")
                cur.execute("DROP TABLE IF EXISTS guideline_migrations CASCADE")
                conn.commit()

        logger.info("Guidelines database reset complete")
        return True

    except Exception as e:
        logger.error(f"Failed to reset guidelines database: {e}")
        return False


if __name__ == "__main__":
    # Run migrations when executed directly
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        status = check_guidelines_schema()
        print("\nGuidelines Database Schema Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
    else:
        success = run_guidelines_migrations()
        sys.exit(0 if success else 1)
