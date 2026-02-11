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

from utils.structured_logging import get_logger
import os
from typing import Optional

from rag.guidelines_env import load_guidelines_env

load_guidelines_env()

logger = get_logger(__name__)


# Migration versions
CURRENT_VERSION = 4

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

    2: """
    -- Migration 2: Add missing columns for databases created with old schema
    -- This handles databases created from setup_guidelines_db.sql which lacks
    -- filename, upload_status, sync tracking columns, etc.

    -- Add filename column if not exists (derive from file_path or title)
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'filename'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN filename TEXT;
            -- Populate filename from file_path or title
            UPDATE guidelines
            SET filename = COALESCE(
                NULLIF(SUBSTRING(file_path FROM '[^/\\\\]+$'), ''),
                title,
                'unknown.pdf'
            )
            WHERE filename IS NULL;
        END IF;
    END $$;

    -- Add file_type column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'file_type'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN file_type VARCHAR(10);
            -- Infer file_type from filename or file_path
            UPDATE guidelines
            SET file_type = LOWER(SUBSTRING(COALESCE(filename, file_path, '') FROM '\\.([^.]+)$'))
            WHERE file_type IS NULL;
        END IF;
    END $$;

    -- Add file_size_bytes column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'file_size_bytes'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN file_size_bytes INTEGER DEFAULT 0;
        END IF;
    END $$;

    -- Add page_count column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'page_count'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN page_count INTEGER DEFAULT 0;
        END IF;
    END $$;

    -- Add chunk_count column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'chunk_count'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN chunk_count INTEGER DEFAULT 0;
            -- Populate chunk_count from actual embedding counts
            UPDATE guidelines g
            SET chunk_count = (
                SELECT COUNT(*) FROM guideline_embeddings ge
                WHERE ge.guideline_id = g.id
            );
        END IF;
    END $$;

    -- Add upload_status column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'upload_status'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN upload_status VARCHAR(20) DEFAULT 'completed';
        END IF;
    END $$;

    -- Add neon_synced column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'neon_synced'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN neon_synced BOOLEAN DEFAULT TRUE;
        END IF;
    END $$;

    -- Add neo4j_synced column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'neo4j_synced'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN neo4j_synced BOOLEAN DEFAULT FALSE;
        END IF;
    END $$;

    -- Add error_message column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'error_message'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN error_message TEXT;
        END IF;
    END $$;

    -- Add expiration_date column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'expiration_date'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN expiration_date DATE;
        END IF;
    END $$;

    -- Add array columns if not exist
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'authors'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN authors TEXT[] DEFAULT '{}';
        END IF;
    END $$;

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'keywords'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN keywords TEXT[] DEFAULT '{}';
        END IF;
    END $$;

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'conditions_covered'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN conditions_covered TEXT[] DEFAULT '{}';
        END IF;
    END $$;

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'medications_covered'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN medications_covered TEXT[] DEFAULT '{}';
        END IF;
    END $$;

    -- Add updated_at column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'updated_at'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
        END IF;
    END $$;

    -- Ensure guideline_migrations table exists (for databases created before migrations)
    CREATE TABLE IF NOT EXISTS guideline_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMPTZ DEFAULT NOW(),
        description TEXT
    );

    -- Record this migration
    INSERT INTO guideline_migrations (version, description)
    VALUES (2, 'Add missing columns for old schema compatibility')
    ON CONFLICT (version) DO NOTHING;
    """,

    3: """
    -- Migration 3: Add content_hash column for duplicate detection by content
    -- Also adds index for fast lookups

    -- Add content_hash column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'content_hash'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN content_hash VARCHAR(32);
        END IF;
    END $$;

    -- Create index on content_hash for fast duplicate detection
    CREATE INDEX IF NOT EXISTS idx_guidelines_content_hash
    ON guidelines (content_hash)
    WHERE content_hash IS NOT NULL;

    -- Record this migration
    INSERT INTO guideline_migrations (version, description)
    VALUES (3, 'Add content_hash column for duplicate detection')
    ON CONFLICT (version) DO NOTHING;
    """,

    4: """
    -- Migration 4: Add versioning/supersession columns and simhash for fuzzy dedup

    -- Add superseded_by column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'superseded_by'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN superseded_by UUID REFERENCES guidelines(id);
        END IF;
    END $$;

    -- Add is_superseded column if not exists
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'is_superseded'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN is_superseded BOOLEAN DEFAULT FALSE;
        END IF;
    END $$;

    -- Add simhash column for fuzzy deduplication
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'guidelines' AND column_name = 'simhash'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN simhash BIGINT;
        END IF;
    END $$;

    -- Index for supersession queries
    CREATE INDEX IF NOT EXISTS idx_guidelines_superseded_by
    ON guidelines (superseded_by)
    WHERE superseded_by IS NOT NULL;

    -- Index for filtering active guidelines
    CREATE INDEX IF NOT EXISTS idx_guidelines_is_superseded
    ON guidelines (is_superseded)
    WHERE is_superseded = TRUE;

    -- Index for simhash lookups
    CREATE INDEX IF NOT EXISTS idx_guidelines_simhash
    ON guidelines (simhash)
    WHERE simhash IS NOT NULL;

    -- Record this migration
    INSERT INTO guideline_migrations (version, description)
    VALUES (4, 'Add versioning/supersession columns and simhash')
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
        from settings.settings import SETTINGS
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


def _check_old_schema_exists(cursor) -> bool:
    """Check if this is an old schema database (tables exist but no migrations table)."""
    try:
        # Check if guidelines table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'guidelines'
            )
        """)
        has_guidelines = cursor.fetchone()[0]

        # Check if migrations table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'guideline_migrations'
            )
        """)
        has_migrations = cursor.fetchone()[0]

        return has_guidelines and not has_migrations
    except Exception:
        return False


def _bootstrap_old_schema(cursor) -> bool:
    """Bootstrap migration tracking for old schema databases.

    For databases created with the old setup_guidelines_db.sql script,
    we need to create the migrations table and mark version 1 as done
    (since the core tables already exist).
    """
    try:
        logger.info("Detected old schema database - bootstrapping migration tracking")

        # Create the migrations tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guideline_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW(),
                description TEXT
            )
        """)

        # Mark version 1 as applied (tables already exist from old schema)
        cursor.execute("""
            INSERT INTO guideline_migrations (version, description)
            VALUES (1, 'Bootstrapped from old schema')
            ON CONFLICT (version) DO NOTHING
        """)

        logger.info("Migration tracking bootstrapped - will run migration 2 to add missing columns")
        return True
    except Exception as e:
        logger.error(f"Failed to bootstrap old schema: {e}")
        return False


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
                # Check for old schema that needs bootstrapping
                if _check_old_schema_exists(cur):
                    if not _bootstrap_old_schema(cursor=cur):
                        conn.rollback()
                        return False
                    conn.commit()

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
    import logging
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
