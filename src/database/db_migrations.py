"""
Database migration system for Medical Assistant.
"""

import logging
import os
import sqlite3
from typing import List, Dict, Optional, Callable
from datetime import datetime
from pathlib import Path

from database.db_pool import get_db_manager
from utils.exceptions import DatabaseError
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class Migration:
    """Represents a database migration."""
    
    def __init__(self, version: int, name: str, up_sql: str, down_sql: Optional[str] = None):
        """Initialize a migration.
        
        Args:
            version: Migration version number
            name: Migration name/description
            up_sql: SQL to apply the migration
            down_sql: SQL to rollback the migration (optional)
        """
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.applied_at = None


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self):
        """Initialize migration manager."""
        self.logger = get_logger(__name__)
        self.db_manager = get_db_manager()
        self._migrations = []
        self._init_migrations_table()
    
    def _init_migrations_table(self):
        """Create the migrations tracking table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db_manager.execute(create_table_sql)
        self.logger.info("Migrations table initialized")
    
    def register(self, migration: Migration):
        """Register a migration.
        
        Args:
            migration: Migration to register
        """
        self._migrations.append(migration)
        self._migrations.sort(key=lambda m: m.version)
    
    def get_current_version(self) -> int:
        """Get the current database schema version.
        
        Returns:
            Current version number or 0 if no migrations applied
        """
        result = self.db_manager.fetchone(
            "SELECT MAX(version) FROM schema_migrations"
        )
        return result[0] if result and result[0] else 0
    
    def get_applied_migrations(self) -> List[Dict]:
        """Get list of applied migrations.
        
        Returns:
            List of applied migration records
        """
        rows = self.db_manager.fetchall(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
        return [
            {"version": row[0], "name": row[1], "applied_at": row[2]}
            for row in rows
        ]
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations.
        
        Returns:
            List of migrations that haven't been applied yet
        """
        current_version = self.get_current_version()
        return [m for m in self._migrations if m.version > current_version]
    
    def migrate(self, target_version: Optional[int] = None) -> int:
        """Apply migrations up to target version.
        
        Args:
            target_version: Target version to migrate to (None = latest)
            
        Returns:
            Number of migrations applied
            
        Raises:
            DatabaseError: If migration fails
        """
        current_version = self.get_current_version()
        pending = self.get_pending_migrations()
        
        if target_version is None:
            target_version = self._migrations[-1].version if self._migrations else 0
        
        if target_version <= current_version:
            self.logger.info(f"Already at version {current_version}, nothing to migrate")
            return 0
        
        applied_count = 0
        
        for migration in pending:
            if migration.version > target_version:
                break
            
            try:
                self._apply_migration(migration)
                applied_count += 1
            except Exception as e:
                self.logger.error(f"Migration {migration.version} failed: {e}")
                raise DatabaseError(f"Migration {migration.version} '{migration.name}' failed: {e}")
        
        self.logger.info(f"Applied {applied_count} migrations, now at version {self.get_current_version()}")
        return applied_count
    
    def _apply_migration(self, migration: Migration):
        """Apply a single migration.

        Args:
            migration: Migration to apply
        """
        self.logger.info(f"Applying migration {migration.version}: {migration.name}")

        with self.db_manager.transaction() as conn:
            # Special handling for migration 12 - conditionally add patient_name column
            if migration.version == 12:
                self._apply_migration_12(conn)
            else:
                # Execute migration SQL
                if ";" in migration.up_sql:
                    # Multiple statements
                    conn.executescript(migration.up_sql)
                else:
                    # Single statement
                    conn.execute(migration.up_sql)

            # Record migration
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name)
            )

    def _apply_migration_12(self, conn):
        """Apply migration 12 with conditional column addition.

        This migration adds the patient_name column if it doesn't exist,
        then creates performance indices.

        Args:
            conn: Database connection within transaction
        """
        # Check if patient_name column already exists
        cursor = conn.execute("PRAGMA table_info(recordings)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'patient_name' not in columns:
            self.logger.info("Adding patient_name column to recordings table")
            conn.execute("ALTER TABLE recordings ADD COLUMN patient_name TEXT")
        else:
            self.logger.info("patient_name column already exists, skipping")

        # Create indices (these use IF NOT EXISTS so they're safe)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recordings_patient_name ON recordings(patient_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recordings_timestamp_desc ON recordings(timestamp DESC)"
        )
    
    def rollback(self, target_version: int = 0) -> int:
        """Rollback migrations to target version.
        
        Args:
            target_version: Target version to rollback to (0 = initial state)
            
        Returns:
            Number of migrations rolled back
            
        Raises:
            DatabaseError: If rollback fails or migration has no down_sql
        """
        current_version = self.get_current_version()
        
        if target_version >= current_version:
            self.logger.info(f"Already at version {current_version}, nothing to rollback")
            return 0
        
        # Get migrations to rollback in reverse order
        to_rollback = [
            m for m in reversed(self._migrations)
            if m.version > target_version and m.version <= current_version
        ]
        
        rolled_back_count = 0
        
        for migration in to_rollback:
            if migration.down_sql is None:
                raise DatabaseError(
                    f"Cannot rollback migration {migration.version} '{migration.name}': "
                    "no down_sql provided"
                )
            
            try:
                self._rollback_migration(migration)
                rolled_back_count += 1
            except Exception as e:
                self.logger.error(f"Rollback of migration {migration.version} failed: {e}")
                raise DatabaseError(
                    f"Rollback of migration {migration.version} '{migration.name}' failed: {e}"
                )
        
        self.logger.info(
            f"Rolled back {rolled_back_count} migrations, now at version {self.get_current_version()}"
        )
        return rolled_back_count
    
    def _rollback_migration(self, migration: Migration):
        """Rollback a single migration.
        
        Args:
            migration: Migration to rollback
        """
        self.logger.info(f"Rolling back migration {migration.version}: {migration.name}")
        
        with self.db_manager.transaction() as conn:
            # Execute rollback SQL
            if ";" in migration.down_sql:
                # Multiple statements
                conn.executescript(migration.down_sql)
            else:
                # Single statement
                conn.execute(migration.down_sql)
            
            # Remove migration record
            conn.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,)
            )


# Define migrations
def get_migrations() -> List[Migration]:
    """Get all database migrations.
    
    Returns:
        List of migrations in order
    """
    migrations = []
    
    # Migration 1: Initial schema
    migrations.append(Migration(
        version=1,
        name="Initial schema",
        up_sql="""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            transcript TEXT,
            soap_note TEXT,
            referral TEXT,
            letter TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        down_sql="DROP TABLE IF EXISTS recordings"
    ))
    
    # Migration 2: Add indexes for search performance
    migrations.append(Migration(
        version=2,
        name="Add search indexes",
        up_sql="""
        CREATE INDEX IF NOT EXISTS idx_recordings_timestamp ON recordings(timestamp);
        CREATE INDEX IF NOT EXISTS idx_recordings_filename ON recordings(filename);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_recordings_timestamp;
        DROP INDEX IF EXISTS idx_recordings_filename;
        """
    ))
    
    # Migration 3: Add full-text search support
    migrations.append(Migration(
        version=3,
        name="Add full-text search",
        up_sql="""
        -- Create virtual table for full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
            transcript,
            soap_note,
            referral,
            letter,
            content=recordings,
            content_rowid=id
        );
        
        -- Create triggers to keep FTS table in sync
        CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
            INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter)
            VALUES (new.id, new.transcript, new.soap_note, new.referral, new.letter);
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_ad AFTER DELETE ON recordings BEGIN
            DELETE FROM recordings_fts WHERE rowid = old.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
            UPDATE recordings_fts 
            SET transcript = new.transcript,
                soap_note = new.soap_note,
                referral = new.referral,
                letter = new.letter
            WHERE rowid = new.id;
        END;
        
        -- Populate FTS table with existing data
        INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter)
        SELECT id, transcript, soap_note, referral, letter FROM recordings;
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS recordings_au;
        DROP TRIGGER IF EXISTS recordings_ad;
        DROP TRIGGER IF EXISTS recordings_ai;
        DROP TABLE IF EXISTS recordings_fts;
        """
    ))
    
    # Migration 4: Add metadata fields
    migrations.append(Migration(
        version=4,
        name="Add metadata fields",
        up_sql="""
        ALTER TABLE recordings ADD COLUMN duration_seconds REAL;
        ALTER TABLE recordings ADD COLUMN file_size_bytes INTEGER;
        ALTER TABLE recordings ADD COLUMN stt_provider TEXT;
        ALTER TABLE recordings ADD COLUMN ai_provider TEXT;
        ALTER TABLE recordings ADD COLUMN tags TEXT;  -- JSON array of tags
        """,
        down_sql=None  # SQLite doesn't support DROP COLUMN easily
    ))
    
    # Migration 5: Add patient information (encrypted)
    migrations.append(Migration(
        version=5,
        name="Add patient information",
        up_sql="""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT UNIQUE NOT NULL,  -- Encrypted patient identifier
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        ALTER TABLE recordings ADD COLUMN patient_id INTEGER REFERENCES patients(id);
        CREATE INDEX IF NOT EXISTS idx_recordings_patient_id ON recordings(patient_id);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_recordings_patient_id;
        DROP TABLE IF EXISTS patients;
        """
    ))
    
    # Migration 6: Add chat column for ChatGPT-style conversations
    migrations.append(Migration(
        version=6,
        name="Add chat column",
        up_sql="""
        ALTER TABLE recordings ADD COLUMN chat TEXT;
        
        -- Update FTS table to include chat
        DROP TRIGGER IF EXISTS recordings_ai;
        DROP TRIGGER IF EXISTS recordings_au;
        DROP TABLE IF EXISTS recordings_fts;
        
        -- Recreate FTS table with chat column
        CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
            transcript,
            soap_note,
            referral,
            letter,
            chat,
            content=recordings,
            content_rowid=id
        );
        
        -- Recreate triggers with chat column
        CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
            INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter, chat)
            VALUES (new.id, new.transcript, new.soap_note, new.referral, new.letter, new.chat);
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_ad AFTER DELETE ON recordings BEGIN
            DELETE FROM recordings_fts WHERE rowid = old.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
            UPDATE recordings_fts 
            SET transcript = new.transcript,
                soap_note = new.soap_note,
                referral = new.referral,
                letter = new.letter,
                chat = new.chat
            WHERE rowid = new.id;
        END;
        
        -- Populate FTS table with existing data
        INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter, chat)
        SELECT id, transcript, soap_note, referral, letter, chat FROM recordings;
        """,
        down_sql=None  # Complex migration, no rollback
    ))
    
    # Migration 7: Add medication management tables
    migrations.append(Migration(
        version=7,
        name="Add medication management tables",
        up_sql="""
        -- Medications reference table
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generic_name TEXT NOT NULL,
            brand_names TEXT,  -- JSON array of brand names
            drug_class TEXT,
            controlled_substance_schedule TEXT,
            form TEXT,  -- tablet, capsule, liquid, etc.
            strengths TEXT,  -- JSON array of available strengths
            routes TEXT,  -- JSON array of administration routes
            common_dosages TEXT,  -- JSON object with indication-based dosing
            contraindications TEXT,  -- JSON array
            warnings TEXT,  -- JSON array
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Patient medications table
        CREATE TABLE IF NOT EXISTS patient_medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER REFERENCES patients(id),
            recording_id INTEGER REFERENCES recordings(id),
            medication_id INTEGER REFERENCES medications(id),
            medication_name TEXT NOT NULL,  -- Free text name as entered
            dose TEXT,
            route TEXT,
            frequency TEXT,
            start_date DATE,
            end_date DATE,
            status TEXT CHECK(status IN ('active', 'discontinued', 'hold', 'completed')),
            indication TEXT,
            prescriber TEXT,
            pharmacy TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Medication history table for tracking changes
        CREATE TABLE IF NOT EXISTS medication_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_medication_id INTEGER REFERENCES patient_medications(id),
            change_type TEXT CHECK(change_type IN ('started', 'modified', 'discontinued', 'restarted')),
            change_reason TEXT,
            previous_dose TEXT,
            new_dose TEXT,
            previous_frequency TEXT,
            new_frequency TEXT,
            changed_by TEXT,
            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Drug interactions table
        CREATE TABLE IF NOT EXISTS drug_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug1_name TEXT NOT NULL,
            drug2_name TEXT NOT NULL,
            severity TEXT CHECK(severity IN ('contraindicated', 'major', 'moderate', 'minor')),
            description TEXT,
            clinical_significance TEXT,
            management TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(drug1_name, drug2_name)
        );
        
        -- Medication alerts table
        CREATE TABLE IF NOT EXISTS medication_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER REFERENCES patients(id),
            alert_type TEXT CHECK(alert_type IN ('allergy', 'interaction', 'duplicate', 'dosing', 'contraindication')),
            severity TEXT CHECK(severity IN ('high', 'medium', 'low')),
            medication_names TEXT,  -- JSON array of involved medications
            description TEXT,
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_by TEXT,
            acknowledged_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_medications_generic ON medications(generic_name);
        CREATE INDEX IF NOT EXISTS idx_patient_meds_patient ON patient_medications(patient_id);
        CREATE INDEX IF NOT EXISTS idx_patient_meds_status ON patient_medications(status);
        CREATE INDEX IF NOT EXISTS idx_patient_meds_recording ON patient_medications(recording_id);
        CREATE INDEX IF NOT EXISTS idx_med_history_patient_med ON medication_history(patient_medication_id);
        CREATE INDEX IF NOT EXISTS idx_interactions_drugs ON drug_interactions(drug1_name, drug2_name);
        CREATE INDEX IF NOT EXISTS idx_alerts_patient ON medication_alerts(patient_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_type ON medication_alerts(alert_type);
        
        -- Create FTS table for medication search
        CREATE VIRTUAL TABLE IF NOT EXISTS medications_fts USING fts5(
            generic_name,
            brand_names,
            drug_class,
            content=medications,
            content_rowid=id
        );
        
        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS medications_ai AFTER INSERT ON medications BEGIN
            INSERT INTO medications_fts(rowid, generic_name, brand_names, drug_class)
            VALUES (new.id, new.generic_name, new.brand_names, new.drug_class);
        END;
        
        CREATE TRIGGER IF NOT EXISTS medications_ad AFTER DELETE ON medications BEGIN
            DELETE FROM medications_fts WHERE rowid = old.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS medications_au AFTER UPDATE ON medications BEGIN
            UPDATE medications_fts 
            SET generic_name = new.generic_name,
                brand_names = new.brand_names,
                drug_class = new.drug_class
            WHERE rowid = new.id;
        END;
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS medications_au;
        DROP TRIGGER IF EXISTS medications_ad;
        DROP TRIGGER IF EXISTS medications_ai;
        DROP TABLE IF EXISTS medications_fts;
        DROP INDEX IF EXISTS idx_alerts_type;
        DROP INDEX IF EXISTS idx_alerts_patient;
        DROP INDEX IF EXISTS idx_interactions_drugs;
        DROP INDEX IF EXISTS idx_med_history_patient_med;
        DROP INDEX IF EXISTS idx_patient_meds_recording;
        DROP INDEX IF EXISTS idx_patient_meds_status;
        DROP INDEX IF EXISTS idx_patient_meds_patient;
        DROP INDEX IF EXISTS idx_medications_generic;
        DROP TABLE IF EXISTS medication_alerts;
        DROP TABLE IF EXISTS drug_interactions;
        DROP TABLE IF EXISTS medication_history;
        DROP TABLE IF EXISTS patient_medications;
        DROP TABLE IF EXISTS medications;
        """
    ))
    
    # Migration 8: Add batch processing support
    migrations.append(Migration(
        version=8,
        name="Add batch processing support",
        up_sql="""
        -- First ensure processing_queue table exists
        CREATE TABLE IF NOT EXISTS processing_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recording_id INTEGER NOT NULL,
            task_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'queued',
            priority INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            result TEXT,
            batch_id TEXT,
            FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE CASCADE
        );
        
        -- Create index for batch queries
        CREATE INDEX IF NOT EXISTS idx_processing_queue_batch_id ON processing_queue(batch_id);
        
        -- Create batch_processing table to track batch metadata
        CREATE TABLE IF NOT EXISTS batch_processing (
            batch_id TEXT PRIMARY KEY,
            total_count INTEGER NOT NULL,
            completed_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            options TEXT,  -- JSON string for batch options
            status TEXT DEFAULT 'pending'
        );
        
        -- Create index for batch status queries
        CREATE INDEX IF NOT EXISTS idx_batch_processing_status ON batch_processing(status);
        """,
        down_sql="""
        -- Remove batch processing support
        DROP INDEX IF EXISTS idx_batch_processing_status;
        DROP TABLE IF EXISTS batch_processing;
        DROP INDEX IF EXISTS idx_processing_queue_batch_id;
        DROP TABLE IF EXISTS processing_queue;
        """
    ))

    # Migration 9: Add saved recipients for referrals
    migrations.append(Migration(
        version=9,
        name="Add saved recipients for referrals",
        up_sql="""
        -- Create saved_recipients table for storing frequently used referral recipients
        CREATE TABLE IF NOT EXISTS saved_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            recipient_type TEXT NOT NULL CHECK(recipient_type IN ('specialist', 'gp_backreferral', 'hospital', 'diagnostic')),
            specialty TEXT,
            facility TEXT,
            address TEXT,
            fax TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT,
            last_used DATETIME,
            use_count INTEGER DEFAULT 0,
            is_favorite BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_saved_recipients_type ON saved_recipients(recipient_type);
        CREATE INDEX IF NOT EXISTS idx_saved_recipients_specialty ON saved_recipients(specialty);
        CREATE INDEX IF NOT EXISTS idx_saved_recipients_last_used ON saved_recipients(last_used);
        CREATE INDEX IF NOT EXISTS idx_saved_recipients_use_count ON saved_recipients(use_count);

        -- Create FTS table for recipient search
        CREATE VIRTUAL TABLE IF NOT EXISTS saved_recipients_fts USING fts5(
            name,
            specialty,
            facility,
            notes,
            content=saved_recipients,
            content_rowid=id
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS saved_recipients_ai AFTER INSERT ON saved_recipients BEGIN
            INSERT INTO saved_recipients_fts(rowid, name, specialty, facility, notes)
            VALUES (new.id, new.name, new.specialty, new.facility, new.notes);
        END;

        CREATE TRIGGER IF NOT EXISTS saved_recipients_ad AFTER DELETE ON saved_recipients BEGIN
            DELETE FROM saved_recipients_fts WHERE rowid = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS saved_recipients_au AFTER UPDATE ON saved_recipients BEGIN
            UPDATE saved_recipients_fts
            SET name = new.name,
                specialty = new.specialty,
                facility = new.facility,
                notes = new.notes
            WHERE rowid = new.id;
        END;
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS saved_recipients_au;
        DROP TRIGGER IF EXISTS saved_recipients_ad;
        DROP TRIGGER IF EXISTS saved_recipients_ai;
        DROP TABLE IF EXISTS saved_recipients_fts;
        DROP INDEX IF EXISTS idx_saved_recipients_use_count;
        DROP INDEX IF EXISTS idx_saved_recipients_last_used;
        DROP INDEX IF EXISTS idx_saved_recipients_specialty;
        DROP INDEX IF EXISTS idx_saved_recipients_type;
        DROP TABLE IF EXISTS saved_recipients;
        """
    ))

    # Migration 10: Add extended contact fields for CSV import
    migrations.append(Migration(
        version=10,
        name="Add extended contact fields for CSV import",
        up_sql="""
        -- Add new columns for detailed contact information
        ALTER TABLE saved_recipients ADD COLUMN first_name TEXT;
        ALTER TABLE saved_recipients ADD COLUMN last_name TEXT;
        ALTER TABLE saved_recipients ADD COLUMN middle_name TEXT;
        ALTER TABLE saved_recipients ADD COLUMN title TEXT;
        ALTER TABLE saved_recipients ADD COLUMN payee_number TEXT;
        ALTER TABLE saved_recipients ADD COLUMN practitioner_number TEXT;
        ALTER TABLE saved_recipients ADD COLUMN office_address TEXT;
        ALTER TABLE saved_recipients ADD COLUMN city TEXT;
        ALTER TABLE saved_recipients ADD COLUMN province TEXT;
        ALTER TABLE saved_recipients ADD COLUMN postal_code TEXT;

        -- Create index for practitioner number lookups
        CREATE INDEX IF NOT EXISTS idx_saved_recipients_practitioner ON saved_recipients(practitioner_number);

        -- Update FTS table to include new searchable fields
        DROP TRIGGER IF EXISTS saved_recipients_au;
        DROP TRIGGER IF EXISTS saved_recipients_ad;
        DROP TRIGGER IF EXISTS saved_recipients_ai;
        DROP TABLE IF EXISTS saved_recipients_fts;

        -- Recreate FTS table with additional fields
        CREATE VIRTUAL TABLE IF NOT EXISTS saved_recipients_fts USING fts5(
            name,
            first_name,
            last_name,
            specialty,
            facility,
            city,
            notes,
            content=saved_recipients,
            content_rowid=id
        );

        -- Recreate triggers with new fields
        CREATE TRIGGER IF NOT EXISTS saved_recipients_ai AFTER INSERT ON saved_recipients BEGIN
            INSERT INTO saved_recipients_fts(rowid, name, first_name, last_name, specialty, facility, city, notes)
            VALUES (new.id, new.name, new.first_name, new.last_name, new.specialty, new.facility, new.city, new.notes);
        END;

        CREATE TRIGGER IF NOT EXISTS saved_recipients_ad AFTER DELETE ON saved_recipients BEGIN
            DELETE FROM saved_recipients_fts WHERE rowid = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS saved_recipients_au AFTER UPDATE ON saved_recipients BEGIN
            UPDATE saved_recipients_fts
            SET name = new.name,
                first_name = new.first_name,
                last_name = new.last_name,
                specialty = new.specialty,
                facility = new.facility,
                city = new.city,
                notes = new.notes
            WHERE rowid = new.id;
        END;

        -- Repopulate FTS table
        INSERT INTO saved_recipients_fts(rowid, name, first_name, last_name, specialty, facility, city, notes)
        SELECT id, name, first_name, last_name, specialty, facility, city, notes FROM saved_recipients;
        """,
        down_sql=None  # Complex migration, no rollback
    ))

    # Migration 11: Add translation sessions support
    migrations.append(Migration(
        version=11,
        name="Add translation sessions support",
        up_sql="""
        -- Create translation sessions table
        CREATE TABLE IF NOT EXISTS translation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            recording_id INTEGER REFERENCES recordings(id),
            patient_language TEXT NOT NULL,
            doctor_language TEXT NOT NULL,
            patient_name TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME
        );

        -- Create translation entries table
        CREATE TABLE IF NOT EXISTS translation_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            entry_id TEXT UNIQUE NOT NULL,
            speaker TEXT NOT NULL CHECK(speaker IN ('patient', 'doctor')),
            timestamp DATETIME NOT NULL,
            original_text TEXT NOT NULL,
            original_language TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            target_language TEXT NOT NULL,
            llm_refined_text TEXT,
            duration_seconds REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES translation_sessions(session_id) ON DELETE CASCADE
        );

        -- Create indexes for efficient queries
        CREATE INDEX IF NOT EXISTS idx_translation_sessions_recording ON translation_sessions(recording_id);
        CREATE INDEX IF NOT EXISTS idx_translation_sessions_created ON translation_sessions(created_at);
        CREATE INDEX IF NOT EXISTS idx_translation_entries_session ON translation_entries(session_id);
        CREATE INDEX IF NOT EXISTS idx_translation_entries_timestamp ON translation_entries(timestamp);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_translation_entries_timestamp;
        DROP INDEX IF EXISTS idx_translation_entries_session;
        DROP INDEX IF EXISTS idx_translation_sessions_created;
        DROP INDEX IF EXISTS idx_translation_sessions_recording;
        DROP TABLE IF EXISTS translation_entries;
        DROP TABLE IF EXISTS translation_sessions;
        """
    ))

    # Migration 12: Add patient_name column and performance indices
    # Note: patient_name may already exist in some databases but not others,
    # so we need a custom migration function to handle this conditionally
    migrations.append(Migration(
        version=12,
        name="Add patient_name column and performance indices",
        up_sql="""
        -- First add patient_name column if it doesn't exist (SQLite doesn't have IF NOT EXISTS for columns)
        -- This will be handled specially in _apply_migration_12

        -- Add index on timestamp DESC for faster list ordering
        CREATE INDEX IF NOT EXISTS idx_recordings_timestamp_desc ON recordings(timestamp DESC);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_recordings_timestamp_desc;
        DROP INDEX IF EXISTS idx_recordings_patient_name;
        """
    ))

    # Migration 13: Add analysis_results table for persisting medical analysis results
    migrations.append(Migration(
        version=13,
        name="Add analysis_results table for medical analysis persistence",
        up_sql="""
        -- Table for storing medical analysis results (medication, diagnostic, workflow)
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recording_id INTEGER,                          -- Optional link to a recording
            analysis_type TEXT NOT NULL,                   -- 'medication', 'diagnostic', 'workflow', etc.
            analysis_subtype TEXT,                         -- e.g., 'comprehensive', 'interactions', 'dosing'
            result_text TEXT NOT NULL,                     -- The analysis result text
            result_json TEXT,                              -- Structured JSON result if available
            metadata_json TEXT,                            -- Additional metadata (model, counts, etc.)
            patient_context_json TEXT,                     -- Patient context used (age, weight, etc.)
            source_type TEXT,                              -- Source of analysis: 'transcript', 'soap', 'custom'
            source_text TEXT,                              -- The input text that was analyzed
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE SET NULL
        );

        -- Indexes for efficient queries
        CREATE INDEX IF NOT EXISTS idx_analysis_recording_id ON analysis_results(recording_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_type ON analysis_results(analysis_type);
        CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_results(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_analysis_type_created ON analysis_results(analysis_type, created_at DESC);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_analysis_type_created;
        DROP INDEX IF EXISTS idx_analysis_created_at;
        DROP INDEX IF EXISTS idx_analysis_type;
        DROP INDEX IF EXISTS idx_analysis_recording_id;
        DROP TABLE IF EXISTS analysis_results;
        """
    ))

    # Migration 14: Enhanced diagnostic analysis with structured differentials and FTS
    migrations.append(Migration(
        version=14,
        name="Enhanced diagnostic analysis with structured differentials and FTS",
        up_sql="""
        -- Table for storing individual differential diagnoses (structured)
        CREATE TABLE IF NOT EXISTS differential_diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            rank INTEGER NOT NULL,                          -- Position in differential list (1 = most likely)
            diagnosis_name TEXT NOT NULL,
            icd10_code TEXT,
            icd9_code TEXT,
            confidence_score REAL,                          -- 0.0 to 1.0 (0-100%)
            confidence_level TEXT,                          -- 'high', 'medium', 'low'
            reasoning TEXT,                                 -- Why this diagnosis is considered
            supporting_findings TEXT,                       -- JSON array of supporting evidence
            against_findings TEXT,                          -- JSON array of findings against
            is_red_flag BOOLEAN DEFAULT FALSE,              -- Urgent/life-threatening
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
        );

        -- Table for storing recommended investigations
        CREATE TABLE IF NOT EXISTS recommended_investigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            investigation_name TEXT NOT NULL,
            investigation_type TEXT,                        -- 'lab', 'imaging', 'procedure', 'referral'
            priority TEXT,                                  -- 'urgent', 'routine', 'optional'
            rationale TEXT,                                 -- Why this investigation is recommended
            target_diagnoses TEXT,                          -- JSON array of diagnosis names this helps rule in/out
            status TEXT DEFAULT 'pending',                  -- 'pending', 'ordered', 'completed', 'cancelled'
            ordered_at TIMESTAMP,
            completed_at TIMESTAMP,
            result_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
        );

        -- Table for storing clinical pearls
        CREATE TABLE IF NOT EXISTS clinical_pearls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            pearl_text TEXT NOT NULL,
            category TEXT,                                  -- 'diagnostic', 'treatment', 'prognosis', 'general'
            source TEXT,                                    -- Where the pearl comes from
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
        );

        -- Table for extracted clinical data (from DataExtractionAgent)
        CREATE TABLE IF NOT EXISTS extracted_clinical_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            data_type TEXT NOT NULL,                        -- 'vital_signs', 'labs', 'medications', 'diagnoses', 'procedures'
            data_json TEXT NOT NULL,                        -- JSON object with extracted data
            extraction_confidence REAL,                     -- How confident the extraction is
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analysis_results(id) ON DELETE CASCADE
        );

        -- Add version tracking columns to analysis_results
        ALTER TABLE analysis_results ADD COLUMN version INTEGER DEFAULT 1;
        ALTER TABLE analysis_results ADD COLUMN parent_analysis_id INTEGER REFERENCES analysis_results(id);
        ALTER TABLE analysis_results ADD COLUMN patient_identifier TEXT;  -- For grouping analyses by patient

        -- Create indexes for efficient queries
        CREATE INDEX IF NOT EXISTS idx_differential_analysis ON differential_diagnoses(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_differential_icd10 ON differential_diagnoses(icd10_code);
        CREATE INDEX IF NOT EXISTS idx_differential_confidence ON differential_diagnoses(confidence_score DESC);
        CREATE INDEX IF NOT EXISTS idx_investigations_analysis ON recommended_investigations(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_investigations_status ON recommended_investigations(status);
        CREATE INDEX IF NOT EXISTS idx_pearls_analysis ON clinical_pearls(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_extracted_data_analysis ON extracted_clinical_data(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_patient ON analysis_results(patient_identifier);
        CREATE INDEX IF NOT EXISTS idx_analysis_parent ON analysis_results(parent_analysis_id);

        -- Create FTS5 table for full-text search on analysis results
        CREATE VIRTUAL TABLE IF NOT EXISTS analysis_results_fts USING fts5(
            result_text,
            source_text,
            content=analysis_results,
            content_rowid=id
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS analysis_results_ai AFTER INSERT ON analysis_results BEGIN
            INSERT INTO analysis_results_fts(rowid, result_text, source_text)
            VALUES (new.id, new.result_text, new.source_text);
        END;

        CREATE TRIGGER IF NOT EXISTS analysis_results_ad AFTER DELETE ON analysis_results BEGIN
            DELETE FROM analysis_results_fts WHERE rowid = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS analysis_results_au AFTER UPDATE ON analysis_results BEGIN
            UPDATE analysis_results_fts
            SET result_text = new.result_text,
                source_text = new.source_text
            WHERE rowid = new.id;
        END;

        -- Populate FTS table with existing data
        INSERT INTO analysis_results_fts(rowid, result_text, source_text)
        SELECT id, result_text, source_text FROM analysis_results;

        -- Create FTS5 table for searching differential diagnoses
        CREATE VIRTUAL TABLE IF NOT EXISTS differential_diagnoses_fts USING fts5(
            diagnosis_name,
            reasoning,
            content=differential_diagnoses,
            content_rowid=id
        );

        -- Triggers for differential diagnoses FTS
        CREATE TRIGGER IF NOT EXISTS differential_ai AFTER INSERT ON differential_diagnoses BEGIN
            INSERT INTO differential_diagnoses_fts(rowid, diagnosis_name, reasoning)
            VALUES (new.id, new.diagnosis_name, new.reasoning);
        END;

        CREATE TRIGGER IF NOT EXISTS differential_ad AFTER DELETE ON differential_diagnoses BEGIN
            DELETE FROM differential_diagnoses_fts WHERE rowid = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS differential_au AFTER UPDATE ON differential_diagnoses BEGIN
            UPDATE differential_diagnoses_fts
            SET diagnosis_name = new.diagnosis_name,
                reasoning = new.reasoning
            WHERE rowid = new.id;
        END;
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS differential_au;
        DROP TRIGGER IF EXISTS differential_ad;
        DROP TRIGGER IF EXISTS differential_ai;
        DROP TABLE IF EXISTS differential_diagnoses_fts;
        DROP TRIGGER IF EXISTS analysis_results_au;
        DROP TRIGGER IF EXISTS analysis_results_ad;
        DROP TRIGGER IF EXISTS analysis_results_ai;
        DROP TABLE IF EXISTS analysis_results_fts;
        DROP INDEX IF EXISTS idx_analysis_parent;
        DROP INDEX IF EXISTS idx_analysis_patient;
        DROP INDEX IF EXISTS idx_extracted_data_analysis;
        DROP INDEX IF EXISTS idx_pearls_analysis;
        DROP INDEX IF EXISTS idx_investigations_status;
        DROP INDEX IF EXISTS idx_investigations_analysis;
        DROP INDEX IF EXISTS idx_differential_confidence;
        DROP INDEX IF EXISTS idx_differential_icd10;
        DROP INDEX IF EXISTS idx_differential_analysis;
        DROP TABLE IF EXISTS extracted_clinical_data;
        DROP TABLE IF EXISTS clinical_pearls;
        DROP TABLE IF EXISTS recommended_investigations;
        DROP TABLE IF EXISTS differential_diagnoses;
        """
    ))

    # Migration 15: RAG Document Management System
    migrations.append(Migration(
        version=15,
        name="RAG Document Management System",
        up_sql="""
        -- Table for tracking uploaded documents
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT UNIQUE NOT NULL,           -- UUID for the document
            filename TEXT NOT NULL,                      -- Original filename
            file_type TEXT NOT NULL,                     -- pdf, docx, txt, image
            file_path TEXT,                              -- Local storage path
            file_size_bytes INTEGER DEFAULT 0,
            page_count INTEGER DEFAULT 0,
            ocr_required BOOLEAN DEFAULT FALSE,
            upload_status TEXT DEFAULT 'pending',        -- pending, extracting, chunking, embedding, syncing, completed, failed
            chunk_count INTEGER DEFAULT 0,
            neon_synced BOOLEAN DEFAULT FALSE,           -- Whether embeddings are in Neon
            graphiti_synced BOOLEAN DEFAULT FALSE,       -- Whether added to knowledge graph
            error_message TEXT,
            metadata_json TEXT,                          -- JSON: title, author, keywords, etc.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Table for document chunks with local text storage
        CREATE TABLE IF NOT EXISTS rag_document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT NOT NULL,                   -- References rag_documents.document_id
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            token_count INTEGER DEFAULT 0,
            start_page INTEGER,                          -- For PDFs
            end_page INTEGER,
            neon_id TEXT,                                -- ID in Neon database
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES rag_documents(document_id) ON DELETE CASCADE,
            UNIQUE(document_id, chunk_index)
        );

        -- Table for tracking RAG search history
        CREATE TABLE IF NOT EXISTS rag_search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            processing_time_ms REAL,
            used_graph_search BOOLEAN DEFAULT FALSE,
            top_k INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Table for caching frequently used embeddings
        CREATE TABLE IF NOT EXISTS rag_embedding_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text_hash TEXT UNIQUE NOT NULL,              -- SHA256 of the text
            embedding_json TEXT NOT NULL,                -- JSON array of floats
            model TEXT NOT NULL,                         -- Embedding model used
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            use_count INTEGER DEFAULT 1
        );

        -- Indexes for efficient queries
        CREATE INDEX IF NOT EXISTS idx_rag_documents_status ON rag_documents(upload_status);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_type ON rag_documents(file_type);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_created ON rag_documents(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_rag_documents_neon_sync ON rag_documents(neon_synced);
        CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_document_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_rag_search_created ON rag_search_history(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_rag_cache_hash ON rag_embedding_cache(text_hash);
        CREATE INDEX IF NOT EXISTS idx_rag_cache_used ON rag_embedding_cache(last_used_at DESC);

        -- Full-text search for document chunks
        CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
            chunk_text,
            content=rag_document_chunks,
            content_rowid=id
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS rag_chunks_ai AFTER INSERT ON rag_document_chunks BEGIN
            INSERT INTO rag_chunks_fts(rowid, chunk_text)
            VALUES (new.id, new.chunk_text);
        END;

        CREATE TRIGGER IF NOT EXISTS rag_chunks_ad AFTER DELETE ON rag_document_chunks BEGIN
            DELETE FROM rag_chunks_fts WHERE rowid = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS rag_chunks_au AFTER UPDATE ON rag_document_chunks BEGIN
            UPDATE rag_chunks_fts
            SET chunk_text = new.chunk_text
            WHERE rowid = new.id;
        END;

        -- Full-text search for document metadata
        CREATE VIRTUAL TABLE IF NOT EXISTS rag_documents_fts USING fts5(
            filename,
            metadata_json,
            content=rag_documents,
            content_rowid=id
        );

        -- Triggers for document FTS
        CREATE TRIGGER IF NOT EXISTS rag_documents_ai AFTER INSERT ON rag_documents BEGIN
            INSERT INTO rag_documents_fts(rowid, filename, metadata_json)
            VALUES (new.id, new.filename, new.metadata_json);
        END;

        CREATE TRIGGER IF NOT EXISTS rag_documents_ad AFTER DELETE ON rag_documents BEGIN
            DELETE FROM rag_documents_fts WHERE rowid = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS rag_documents_au AFTER UPDATE ON rag_documents BEGIN
            UPDATE rag_documents_fts
            SET filename = new.filename,
                metadata_json = new.metadata_json
            WHERE rowid = new.id;
        END;
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS rag_documents_au;
        DROP TRIGGER IF EXISTS rag_documents_ad;
        DROP TRIGGER IF EXISTS rag_documents_ai;
        DROP TABLE IF EXISTS rag_documents_fts;
        DROP TRIGGER IF EXISTS rag_chunks_au;
        DROP TRIGGER IF EXISTS rag_chunks_ad;
        DROP TRIGGER IF EXISTS rag_chunks_ai;
        DROP TABLE IF EXISTS rag_chunks_fts;
        DROP INDEX IF EXISTS idx_rag_cache_used;
        DROP INDEX IF EXISTS idx_rag_cache_hash;
        DROP INDEX IF EXISTS idx_rag_search_created;
        DROP INDEX IF EXISTS idx_rag_chunks_document;
        DROP INDEX IF EXISTS idx_rag_documents_neon_sync;
        DROP INDEX IF EXISTS idx_rag_documents_created;
        DROP INDEX IF EXISTS idx_rag_documents_type;
        DROP INDEX IF EXISTS idx_rag_documents_status;
        DROP TABLE IF EXISTS rag_embedding_cache;
        DROP TABLE IF EXISTS rag_search_history;
        DROP TABLE IF EXISTS rag_document_chunks;
        DROP TABLE IF EXISTS rag_documents;
        """
    ))

    # Migration 16: RAG Conversation Context and Feedback System
    migrations.append(Migration(
        version=16,
        name="RAG conversation context and feedback system",
        up_sql="""
        -- Conversation sessions with summaries
        CREATE TABLE IF NOT EXISTS rag_conversation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            exchange_count INTEGER DEFAULT 0,
            summary_text TEXT,
            key_topics_json TEXT,
            key_entities_json TEXT
        );

        -- Individual exchanges with embeddings
        CREATE TABLE IF NOT EXISTS rag_conversation_exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            exchange_index INTEGER NOT NULL,
            query_text TEXT NOT NULL,
            query_embedding_json TEXT,
            response_summary TEXT,
            extracted_entities_json TEXT,
            is_followup BOOLEAN DEFAULT FALSE,
            followup_confidence REAL,
            intent_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES rag_conversation_sessions(session_id),
            UNIQUE(session_id, exchange_index)
        );

        -- User feedback on results
        CREATE TABLE IF NOT EXISTS rag_result_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_document_id TEXT NOT NULL,
            result_chunk_index INTEGER NOT NULL,
            feedback_type TEXT NOT NULL CHECK(feedback_type IN ('upvote', 'downvote', 'flag')),
            feedback_reason TEXT,
            original_score REAL,
            query_text TEXT,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Aggregated feedback for relevance boosting
        CREATE TABLE IF NOT EXISTS rag_feedback_aggregates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            upvote_count INTEGER DEFAULT 0,
            downvote_count INTEGER DEFAULT 0,
            relevance_boost REAL DEFAULT 0.0,
            last_calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, chunk_index)
        );

        -- Named entities extracted from queries
        CREATE TABLE IF NOT EXISTS rag_named_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_text TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            normalized_name TEXT,
            confidence REAL,
            source_type TEXT,
            source_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_conv_sessions_activity ON rag_conversation_sessions(last_activity_at);
        CREATE INDEX IF NOT EXISTS idx_conv_exchanges_session ON rag_conversation_exchanges(session_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_document ON rag_result_feedback(result_document_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_agg_doc ON rag_feedback_aggregates(document_id);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON rag_named_entities(entity_type);
        CREATE INDEX IF NOT EXISTS idx_entities_text ON rag_named_entities(entity_text);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_entities_text;
        DROP INDEX IF EXISTS idx_entities_type;
        DROP INDEX IF EXISTS idx_feedback_agg_doc;
        DROP INDEX IF EXISTS idx_feedback_document;
        DROP INDEX IF EXISTS idx_conv_exchanges_session;
        DROP INDEX IF EXISTS idx_conv_sessions_activity;
        DROP TABLE IF EXISTS rag_named_entities;
        DROP TABLE IF EXISTS rag_feedback_aggregates;
        DROP TABLE IF EXISTS rag_result_feedback;
        DROP TABLE IF EXISTS rag_conversation_exchanges;
        DROP TABLE IF EXISTS rag_conversation_sessions;
        """
    ))

    # Migration 17: Knowledge Graph Entity Clusters and Relationship Confidence
    migrations.append(Migration(
        version=17,
        name="Knowledge Graph entity clusters and relationship confidence",
        up_sql="""
        -- Entity clusters for cross-document entity deduplication
        CREATE TABLE IF NOT EXISTS entity_clusters (
            id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            variants_json TEXT,                              -- JSON array of text variants
            source_documents_json TEXT,                      -- JSON array of document IDs
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mention_count INTEGER DEFAULT 1,
            confidence REAL DEFAULT 1.0,
            embedding_json TEXT                              -- Canonical embedding vector
        );

        -- Graph relationships with confidence tracking
        CREATE TABLE IF NOT EXISTS graph_relationships (
            id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL,                  -- References entity_clusters.id
            target_entity_id TEXT NOT NULL,                  -- References entity_clusters.id
            relationship_type TEXT NOT NULL,
            fact TEXT,
            confidence REAL DEFAULT 1.0,
            evidence_count INTEGER DEFAULT 1,
            source_documents_json TEXT,                      -- JSON array of source document IDs
            evidence_type TEXT DEFAULT 'inferred',           -- explicit, inferred, aggregated
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_entity_id, target_entity_id, relationship_type)
        );

        -- Indexes for efficient queries
        CREATE INDEX IF NOT EXISTS idx_entity_clusters_name ON entity_clusters(canonical_name);
        CREATE INDEX IF NOT EXISTS idx_entity_clusters_type ON entity_clusters(entity_type);
        CREATE INDEX IF NOT EXISTS idx_entity_clusters_confidence ON entity_clusters(confidence DESC);
        CREATE INDEX IF NOT EXISTS idx_entity_clusters_mentions ON entity_clusters(mention_count DESC);

        CREATE INDEX IF NOT EXISTS idx_graph_rel_source ON graph_relationships(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_graph_rel_target ON graph_relationships(target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_graph_rel_type ON graph_relationships(relationship_type);
        CREATE INDEX IF NOT EXISTS idx_graph_rel_confidence ON graph_relationships(confidence DESC);
        CREATE INDEX IF NOT EXISTS idx_graph_rel_evidence ON graph_relationships(evidence_count DESC);

        -- Full-text search for entity clusters
        CREATE VIRTUAL TABLE IF NOT EXISTS entity_clusters_fts USING fts5(
            canonical_name,
            variants_json,
            content=entity_clusters,
            content_rowid=rowid
        );

        -- Triggers to keep entity FTS in sync
        CREATE TRIGGER IF NOT EXISTS entity_clusters_ai AFTER INSERT ON entity_clusters BEGIN
            INSERT INTO entity_clusters_fts(rowid, canonical_name, variants_json)
            SELECT rowid, new.canonical_name, new.variants_json FROM entity_clusters WHERE id = new.id;
        END;

        CREATE TRIGGER IF NOT EXISTS entity_clusters_ad AFTER DELETE ON entity_clusters BEGIN
            DELETE FROM entity_clusters_fts WHERE rowid = old.rowid;
        END;

        CREATE TRIGGER IF NOT EXISTS entity_clusters_au AFTER UPDATE ON entity_clusters BEGIN
            UPDATE entity_clusters_fts
            SET canonical_name = new.canonical_name,
                variants_json = new.variants_json
            WHERE rowid = new.rowid;
        END;

        -- Temporal index for time-based queries
        CREATE INDEX IF NOT EXISTS idx_entity_clusters_last_seen ON entity_clusters(last_seen DESC);
        CREATE INDEX IF NOT EXISTS idx_graph_rel_last_seen ON graph_relationships(last_seen DESC);
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS entity_clusters_au;
        DROP TRIGGER IF EXISTS entity_clusters_ad;
        DROP TRIGGER IF EXISTS entity_clusters_ai;
        DROP TABLE IF EXISTS entity_clusters_fts;
        DROP INDEX IF EXISTS idx_graph_rel_last_seen;
        DROP INDEX IF EXISTS idx_entity_clusters_last_seen;
        DROP INDEX IF EXISTS idx_graph_rel_evidence;
        DROP INDEX IF EXISTS idx_graph_rel_confidence;
        DROP INDEX IF EXISTS idx_graph_rel_type;
        DROP INDEX IF EXISTS idx_graph_rel_target;
        DROP INDEX IF EXISTS idx_graph_rel_source;
        DROP INDEX IF EXISTS idx_entity_clusters_mentions;
        DROP INDEX IF EXISTS idx_entity_clusters_confidence;
        DROP INDEX IF EXISTS idx_entity_clusters_type;
        DROP INDEX IF EXISTS idx_entity_clusters_name;
        DROP TABLE IF EXISTS graph_relationships;
        DROP TABLE IF EXISTS entity_clusters;
        """
    ))

    return migrations


# Global migration manager
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """Get the global migration manager.
    
    Returns:
        MigrationManager: Global migration manager instance
    """
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager()
        # Register all migrations
        for migration in get_migrations():
            _migration_manager.register(migration)
    return _migration_manager


def run_migrations():
    """Run all pending migrations."""
    manager = get_migration_manager()

    current_version = manager.get_current_version()
    pending = manager.get_pending_migrations()

    if not pending:
        logger.info(f"Database is up to date (version {current_version})")
        return

    logger.info(f"Current database version: {current_version}")
    logger.info(f"Found {len(pending)} pending migrations:")
    for migration in pending:
        logger.info(f"  - Version {migration.version}: {migration.name}")

    # Apply migrations
    try:
        applied = manager.migrate()
        logger.info(f"Successfully applied {applied} migrations")
        logger.info(f"Database is now at version {manager.get_current_version()}")
    except DatabaseError as e:
        logger.error(f"Error applying migrations: {e}")
        raise


if __name__ == "__main__":
    # Run migrations when executed directly
    logging.basicConfig(level=logging.INFO)
    run_migrations()