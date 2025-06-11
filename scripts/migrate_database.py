#!/usr/bin/env python3
"""
Database migration utility for Medical Assistant.
Migrates existing databases to the new schema with indexes and full-text search.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from datetime import datetime

from config import get_config
from db_migrations import get_migration_manager, run_migrations
from database_v2 import ImprovedDatabase


def backup_database(db_path: Path) -> Path:
    """Create a backup of the existing database.
    
    Args:
        db_path: Path to database file
        
    Returns:
        Path to backup file
    """
    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return None
    
    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(f".backup_{timestamp}.db")
    
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    return backup_path


def migrate_database():
    """Migrate the database to the new schema."""
    print("Medical Assistant Database Migration")
    print("=" * 50)
    
    # Get database path from config
    config = get_config()
    db_path = Path(config.storage.base_folder) / config.storage.database_name
    
    print(f"Database path: {db_path}")
    
    # Check if database exists
    if not db_path.exists():
        print("\nNo existing database found. A new database will be created with the latest schema.")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return
    else:
        # Create backup
        backup_path = backup_database(db_path)
        if backup_path:
            print(f"✓ Backup created successfully")
        else:
            print("Failed to create backup. Migration cancelled.")
            return
    
    try:
        # Initialize migration manager
        print("\nChecking current database version...")
        manager = get_migration_manager()
        
        current_version = manager.get_current_version()
        pending = manager.get_pending_migrations()
        
        print(f"Current version: {current_version}")
        print(f"Latest version: {manager._migrations[-1].version if manager._migrations else 0}")
        
        if not pending:
            print("\n✓ Database is already up to date!")
            return
        
        print(f"\nFound {len(pending)} pending migrations:")
        for migration in pending:
            print(f"  {migration.version}: {migration.name}")
        
        # Confirm migration
        print("\nThis will apply the following changes:")
        print("- Add indexes for better search performance")
        print("- Enable full-text search capabilities")
        print("- Add metadata fields for recordings")
        print("- Add support for patient information")
        
        response = input("\nProceed with migration? (y/n): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return
        
        # Run migrations
        print("\nApplying migrations...")
        run_migrations()
        
        # Verify migration
        new_version = manager.get_current_version()
        print(f"\n✓ Migration completed successfully!")
        print(f"Database is now at version {new_version}")
        
        # Test the database
        print("\nTesting database connection...")
        db = ImprovedDatabase()
        with db.transaction():
            stats = db.get_recording_stats()
            print(f"✓ Database contains {stats['total_recordings']} recordings")
        
        print("\nMigration completed successfully!")
        print(f"Backup saved at: {backup_path}")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print("\nYour original database has been preserved.")
        print("Please check the error and try again.")
        logging.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


def check_database_status():
    """Check the current database status."""
    config = get_config()
    db_path = Path(config.storage.base_folder) / config.storage.database_name
    
    print("Database Status Check")
    print("=" * 50)
    print(f"Database path: {db_path}")
    print(f"Exists: {db_path.exists()}")
    
    if db_path.exists():
        print(f"Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        try:
            manager = get_migration_manager()
            current_version = manager.get_current_version()
            applied = manager.get_applied_migrations()
            
            print(f"\nSchema version: {current_version}")
            print(f"Applied migrations: {len(applied)}")
            
            if applied:
                print("\nMigration history:")
                for m in applied:
                    print(f"  v{m['version']}: {m['name']} (applied {m['applied_at']})")
            
            # Get stats
            db = ImprovedDatabase()
            with db.transaction():
                stats = db.get_recording_stats()
                
            print(f"\nRecording statistics:")
            print(f"  Total recordings: {stats['total_recordings']}")
            
            if stats['total_duration_seconds']:
                hours = stats['total_duration_seconds'] / 3600
                print(f"  Total duration: {hours:.1f} hours")
            
            if stats['total_file_size_bytes']:
                gb = stats['total_file_size_bytes'] / 1024 / 1024 / 1024
                print(f"  Total file size: {gb:.2f} GB")
            
            if stats['by_stt_provider']:
                print(f"\n  By STT provider:")
                for provider, count in stats['by_stt_provider'].items():
                    print(f"    {provider}: {count}")
            
        except Exception as e:
            print(f"\nError reading database: {e}")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_database_status()
    else:
        migrate_database()