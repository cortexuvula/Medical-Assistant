#!/usr/bin/env python3
"""
Run PostgreSQL migration for guidelines database.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg

# Load environment variables
load_dotenv()

def run_migration():
    """Run the guidelines database migration."""

    db_url = os.getenv("CLINICAL_GUIDELINES_DATABASE_URL")
    if not db_url:
        print("❌ CLINICAL_GUIDELINES_DATABASE_URL not set")
        return False

    # Read migration SQL
    sql_file = Path(__file__).parent / "setup_guidelines_db.sql"
    if not sql_file.exists():
        print(f"❌ Migration file not found: {sql_file}")
        return False

    sql_content = sql_file.read_text()

    print(f"Running migration from: {sql_file}")
    print(f"Database: {db_url.split('@')[-1].split('?')[0]}")
    print()

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Execute the migration
                cur.execute(sql_content)
                conn.commit()

                print("✅ Migration completed successfully!")
                return True

    except Exception as e:
        print(f"❌ Migration failed: {type(e).__name__}")
        print(f"   Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
