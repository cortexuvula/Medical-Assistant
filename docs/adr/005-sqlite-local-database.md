# ADR-005: SQLite for Local Data Storage

## Status

Accepted

## Date

2024-01

## Context

Medical Assistant needs persistent local storage for:

- **Recordings metadata**: Timestamps, patient info, file paths
- **Transcripts**: Raw transcription text
- **Generated documents**: SOAP notes, referral letters, clinical letters
- **Processing queue**: Background task management
- **User preferences**: Settings that don't fit in JSON config

Requirements:
- Must work offline (no network dependency for core functionality)
- Must support full-text search across transcripts
- Must handle concurrent access (background processing + UI)
- Must be portable (no separate database server installation)
- PHI (Protected Health Information) stays on user's machine

## Decision

We chose **SQLite** as the local database with:

- **FTS5** (Full-Text Search 5) for transcript searching
- **Connection pooling** for thread safety
- **Version-controlled migrations** for schema evolution

```
src/database/
├── database.py          # Main Database class
├── db_pool.py           # ConnectionPool for thread safety
├── db_migrations.py     # Schema migrations (version 1-8+)
├── schema.py            # Table definitions
└── mixins/              # Feature-specific query methods
    ├── recording_mixin.py
    ├── queue_mixin.py
    └── analysis_mixin.py
```

## Consequences

### Positive

- **Zero configuration**: No database server to install or manage
- **Portable**: Single file, easy to backup or move
- **Fast**: Sub-millisecond reads for typical queries
- **Reliable**: ACID transactions, crash recovery via WAL
- **FTS5**: Powerful full-text search with ranking
- **Python stdlib**: `sqlite3` module included with Python
- **File permissions**: Database file secured with 0600 permissions (owner only)
- **Thread-safe**: Connection pooling handles concurrent access
- **Offline-first**: Works without network connectivity

### Negative

- **Single-writer**: Only one write transaction at a time (mitigated by WAL mode)
- **No network access**: Can't share database across machines directly
- **Limited concurrency**: Heavy concurrent writes could bottleneck
- **No stored procedures**: Complex logic must be in Python
- **Migration complexity**: Schema changes require careful migration code

### Neutral

- Database file stored in user's AppData/data folder
- WAL mode enabled for better concurrent read performance
- Automatic vacuum to reclaim space

## Schema Overview

### Core Tables

```sql
-- Main recordings table
CREATE TABLE recordings (
    id INTEGER PRIMARY KEY,
    patient_name TEXT,
    timestamp TEXT NOT NULL,
    duration_seconds REAL,
    transcript TEXT,
    soap_note TEXT,
    referral_letter TEXT,
    letter TEXT,
    audio_path TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search index
CREATE VIRTUAL TABLE recordings_fts USING fts5(
    patient_name,
    transcript,
    soap_note,
    referral_letter,
    letter,
    content='recordings',
    content_rowid='id'
);

-- Background processing queue
CREATE TABLE processing_queue (
    id INTEGER PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    recording_id INTEGER,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    batch_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recording_id) REFERENCES recordings(id)
);
```

## Alternatives Considered

### PostgreSQL (Local or Remote)

**Rejected because:**
- Requires separate server installation
- Overkill for single-user desktop application
- Adds deployment complexity
- Network dependency if remote

### MongoDB / Document Database

**Rejected because:**
- Requires separate server
- Schema-less nature doesn't fit structured medical data
- Full-text search less mature than SQLite FTS5
- Heavier resource usage

### JSON Files

**Rejected because:**
- No ACID transactions
- Full-text search would require custom implementation
- Concurrent access is error-prone
- Performance degrades with data growth

### LevelDB / RocksDB

**Rejected because:**
- Key-value only, no SQL queries
- No built-in full-text search
- More complex to query relationships
- Less familiar to contributors

### Realm / ObjectBox

**Rejected because:**
- Additional dependencies
- Mobile-focused, less common on desktop
- Proprietary aspects
- Smaller community

## Implementation Details

### Connection Pooling

```python
class ConnectionPool:
    """Thread-safe SQLite connection pool."""

    def __init__(self, database_path: str, pool_size: int = 10):
        self._pool = queue.Queue(maxsize=pool_size)
        self._all_connections: List[sqlite3.Connection] = []
        self._lock = threading.RLock()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._pool.get(timeout=self.timeout)
        try:
            yield conn
        finally:
            self._pool.put(conn)
```

### Migrations

```python
MIGRATIONS = {
    1: """
        CREATE TABLE recordings (...);
        CREATE VIRTUAL TABLE recordings_fts USING fts5(...);
    """,
    2: """
        ALTER TABLE recordings ADD COLUMN audio_path TEXT;
    """,
    # ... up to version 8+
}

def run_migrations(conn: sqlite3.Connection):
    current_version = get_schema_version(conn)
    for version in sorted(MIGRATIONS.keys()):
        if version > current_version:
            conn.executescript(MIGRATIONS[version])
            set_schema_version(conn, version)
```

### Security

- Database file permissions set to 0600 (owner read/write only)
- WAL and SHM files also secured
- No sensitive data in SQL queries logged

### FTS5 Search

```python
def search_recordings(self, query: str) -> List[Dict]:
    """Full-text search across all text fields."""
    return self.fetchall("""
        SELECT r.*, bm25(recordings_fts) as rank
        FROM recordings r
        JOIN recordings_fts fts ON r.id = fts.rowid
        WHERE recordings_fts MATCH ?
        ORDER BY rank
        LIMIT 50
    """, (query,))
```

## References

- [SQLite Documentation](https://sqlite.org/docs.html)
- [FTS5 Full-Text Search](https://sqlite.org/fts5.html)
- [WAL Mode](https://sqlite.org/wal.html)
- [src/database/](../../src/database/) - Database implementation
