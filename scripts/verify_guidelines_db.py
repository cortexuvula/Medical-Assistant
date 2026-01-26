#!/usr/bin/env python3
"""
Verify Guidelines Database Schema
Checks PostgreSQL schema after running setup_guidelines_db.sql migration.
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import psycopg

# Load environment variables
load_dotenv()

def verify_guidelines_db():
    """Verify PostgreSQL guidelines database schema."""

    print("=" * 80)
    print("Guidelines Database Schema Verification")
    print("=" * 80)

    db_url = os.getenv("CLINICAL_GUIDELINES_DATABASE_URL")

    if not db_url:
        print("\n❌ FAILED: CLINICAL_GUIDELINES_DATABASE_URL not set")
        return False

    print(f"\nDatabase: {db_url.split('@')[-1].split('?')[0] if '@' in db_url else 'N/A'}")

    try:
        print("\n🔄 Connecting to database...")
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("✅ Connection successful")

                # Check extensions
                print("\n📦 Checking extensions...")
                cur.execute("""
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname IN ('vector', 'uuid-ossp')
                    ORDER BY extname
                """)
                extensions = cur.fetchall()

                expected_extensions = {'vector', 'uuid-ossp'}
                found_extensions = {ext[0] for ext in extensions}

                for ext_name, ext_version in extensions:
                    print(f"   ✓ {ext_name} v{ext_version}")

                missing = expected_extensions - found_extensions
                if missing:
                    print(f"   ❌ Missing extensions: {', '.join(missing)}")
                    print("\n📋 Run migration script:")
                    print('   psql "$CLINICAL_GUIDELINES_DATABASE_URL" -f scripts/setup_guidelines_db.sql')
                    return False

                # Check tables
                print("\n📊 Checking tables...")
                cur.execute("""
                    SELECT tablename,
                           pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename IN ('guidelines', 'guideline_embeddings')
                    ORDER BY tablename
                """)
                tables = cur.fetchall()

                expected_tables = {'guidelines', 'guideline_embeddings'}
                found_tables = {table[0] for table in tables}

                for table_name, size in tables:
                    # Get row count
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cur.fetchone()[0]
                    print(f"   ✓ {table_name} ({count} rows, {size})")

                missing = expected_tables - found_tables
                if missing:
                    print(f"   ❌ Missing tables: {', '.join(missing)}")
                    print("\n📋 Run migration script:")
                    print('   psql "$CLINICAL_GUIDELINES_DATABASE_URL" -f scripts/setup_guidelines_db.sql')
                    return False

                # Check indexes
                print("\n🔍 Checking indexes...")
                cur.execute("""
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND tablename IN ('guidelines', 'guideline_embeddings')
                    ORDER BY tablename, indexname
                """)
                indexes = cur.fetchall()

                # Critical indexes
                critical_indexes = {
                    'idx_guideline_embeddings_vector',  # HNSW vector search
                    'idx_guideline_embeddings_search',  # GIN full-text search
                }

                found_critical = {idx[0] for idx in indexes if idx[0] in critical_indexes}

                for idx_name, table_name in indexes:
                    status = "✓" if idx_name in critical_indexes else " "
                    print(f"   {status} {table_name}.{idx_name}")

                missing_critical = critical_indexes - found_critical
                if missing_critical:
                    print(f"\n   ⚠️  Missing critical indexes: {', '.join(missing_critical)}")
                    print("   These are required for performance!")

                # Check triggers
                print("\n⚡ Checking triggers...")
                cur.execute("""
                    SELECT trigger_name, event_object_table, action_statement
                    FROM information_schema.triggers
                    WHERE trigger_schema = 'public'
                    AND event_object_table IN ('guidelines', 'guideline_embeddings')
                    ORDER BY event_object_table, trigger_name
                """)
                triggers = cur.fetchall()

                if triggers:
                    for trigger_name, table_name, _ in triggers:
                        print(f"   ✓ {table_name}.{trigger_name}")
                else:
                    print("   ⚠️  No triggers found (expected 2)")

                # Verify schema
                print("\n📋 Schema verification:")

                # Check guidelines table columns
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'guidelines'
                    ORDER BY ordinal_position
                """)
                guidelines_cols = {col[0] for col in cur.fetchall()}
                required_guidelines_cols = {'id', 'title', 'specialty', 'source', 'created_at'}

                if required_guidelines_cols.issubset(guidelines_cols):
                    print("   ✓ guidelines table schema correct")
                else:
                    missing = required_guidelines_cols - guidelines_cols
                    print(f"   ❌ guidelines table missing columns: {missing}")

                # Check guideline_embeddings table columns
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'guideline_embeddings'
                    ORDER BY ordinal_position
                """)
                embeddings_cols = {col[0] for col in cur.fetchall()}
                required_embeddings_cols = {'id', 'guideline_id', 'chunk_text', 'embedding', 'search_vector'}

                if required_embeddings_cols.issubset(embeddings_cols):
                    print("   ✓ guideline_embeddings table schema correct")
                else:
                    missing = required_embeddings_cols - embeddings_cols
                    print(f"   ❌ guideline_embeddings table missing columns: {missing}")

                print("\n✅ Database schema verification complete!")
                print("\n📊 Summary:")
                print(f"   Extensions: {len(found_extensions)}/2")
                print(f"   Tables: {len(found_tables)}/2")
                print(f"   Critical indexes: {len(found_critical)}/{len(critical_indexes)}")
                print(f"   Triggers: {len(triggers)}")

                return True

    except Exception as e:
        print(f"\n❌ Verification failed: {type(e).__name__}")
        print(f"   Error: {str(e)}")

        print("\n📋 Troubleshooting:")
        print("1. Run the migration script:")
        print('   psql "$CLINICAL_GUIDELINES_DATABASE_URL" -f scripts/setup_guidelines_db.sql')
        print("\n2. Verify database URL is correct")
        print("\n3. Check database permissions")
        print("\n4. Install required packages:")
        print("   pip install 'psycopg[binary]>=3.0.0' pgvector")

        return False

if __name__ == "__main__":
    success = verify_guidelines_db()
    sys.exit(0 if success else 1)
