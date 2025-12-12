# Code Review Task Plan

Generated: 2025-12-11

This plan addresses 10 issues identified in the comprehensive code review, organized by priority and estimated effort.

---

## Sprint 1: Critical Security & Stability (Immediate)

### Task 1.1: Fix SQL Injection in Database Migrations
**Priority**: 🔴 CRITICAL | **Effort**: 30 min | **Risk**: High

**Location**: `src/database/db_queue_schema.py:134, 201`

**Problem**: F-strings used to construct SQL statements for ALTER TABLE and CREATE INDEX.

**Solution**:
```python
# Add allowlist validation at top of file
ALLOWED_COLUMNS = {
    'batch_id': 'TEXT',
    'processing_status': 'TEXT',
    # ... other columns
}

ALLOWED_INDEXES = {
    'idx_processing_queue_batch': 'processing_queue(batch_id)',
    # ... other indexes
}

# Before executing:
if column_name not in ALLOWED_COLUMNS:
    raise ValueError(f"Invalid column name: {column_name}")
```

**Acceptance Criteria**:
- [ ] All dynamic SQL uses validated identifiers from allowlists
- [ ] Unit test verifies rejection of invalid identifiers
- [ ] No runtime behavior changes for valid migrations

---

### Task 1.2: Fix Memory Leak in RateLimiter
**Priority**: 🔴 CRITICAL | **Effort**: 2 hours | **Risk**: Medium

**Location**: `src/utils/security.py:502-543, 638-683`

**Problem**: `_key_locks` dictionary grows without bounds as new keys are used.

**Solution**:
```python
class RateLimiter:
    MAX_LOCKS = 1000  # Existing constant
    LOCK_EXPIRY_SECONDS = 3600  # New: 1 hour

    def __init__(self):
        self._key_locks: Dict[str, Tuple[Lock, float]] = {}  # Add timestamp
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def _get_key_lock(self, key: str) -> Lock:
        with self._global_lock:
            now = time.time()

            # Periodic cleanup
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired_locks(now)
                self._last_cleanup = now

            if key not in self._key_locks:
                self._key_locks[key] = (Lock(), now)
            else:
                # Update last access time
                lock, _ = self._key_locks[key]
                self._key_locks[key] = (lock, now)

            return self._key_locks[key][0]

    def _cleanup_expired_locks(self, now: float):
        expired = [k for k, (_, ts) in self._key_locks.items()
                   if now - ts > self.LOCK_EXPIRY_SECONDS]
        for key in expired:
            del self._key_locks[key]
```

**Acceptance Criteria**:
- [ ] Lock count stays bounded during extended operation
- [ ] No deadlocks introduced by cleanup
- [ ] Unit test simulates high key churn and verifies cleanup

---

### Task 1.3: Fix Race Condition in RecordingController
**Priority**: 🔴 CRITICAL | **Effort**: 3 hours | **Risk**: High

**Location**: `src/core/recording_controller.py:56-97, 111-143`

**Problem**: Dual state tracking between `recording_manager.is_recording` and `self._soap_recording`.

**Solution**: Single source of truth pattern
```python
class RecordingController:
    def __init__(self, app: 'MedicalDictationApp'):
        self.app = app
        self._state_lock = threading.Lock()
        # Remove _soap_recording - use recording_manager as single source

    @property
    def is_recording(self) -> bool:
        """Single source of truth for recording state."""
        return self.app.recording_manager.is_recording

    def toggle_recording(self) -> None:
        with self._state_lock:
            if not self.is_recording:
                self._start_recording()
            else:
                self._stop_recording()

    def _start_recording(self) -> None:
        # All state changes happen atomically within recording_manager
        success = self.app.recording_manager.start_recording(self._soap_callback)
        if not success:
            self.app.status_manager.error("Failed to start recording")
            return
        # UI updates only after confirmed success
        self.app._update_recording_ui_state(recording=True, caller="start")
```

**Acceptance Criteria**:
- [ ] Only `recording_manager.is_recording` used as state source
- [ ] All state changes protected by lock
- [ ] UI always reflects actual recording state
- [ ] Manual test: rapid start/stop doesn't cause desync

---

### Task 1.4: Fix Audio Stream Resource Leak
**Priority**: 🔴 CRITICAL | **Effort**: 2 hours | **Risk**: Medium

**Location**: `src/audio/audio.py:168-203, 561-608`

**Problem**: `_active_streams` class variable not cleaned up when instances are destroyed.

**Solution**:
```python
class AudioHandler:
    _active_streams: Dict[str, Any] = {}
    _streams_lock = threading.Lock()

    def __init__(self):
        self._instance_streams: Set[str] = set()  # Track this instance's streams

    def listen_in_background(self, ..., stream_purpose: str = "default") -> Callable:
        with self._streams_lock:
            # Stop existing stream for this purpose
            if stream_purpose in self._active_streams:
                self._stop_stream(stream_purpose)

            # Create new stream
            # ... existing code ...

            self._active_streams[stream_purpose] = stopper
            self._instance_streams.add(stream_purpose)  # Track ownership

        return stopper

    def cleanup_resources(self) -> None:
        """Clean up all streams owned by this instance."""
        with self._streams_lock:
            for purpose in list(self._instance_streams):
                self._stop_stream(purpose)
            self._instance_streams.clear()

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        try:
            self.cleanup_resources()
        except Exception:
            pass  # Don't raise in __del__
```

**Acceptance Criteria**:
- [ ] Each AudioHandler instance tracks its own streams
- [ ] Streams are released when instance is destroyed
- [ ] No "device busy" errors after app restart
- [ ] Manual test: create/destroy multiple AudioHandler instances

---

## Sprint 2: Reliability & Data Integrity (High Priority)

### Task 2.1: Fix Connection Pool Deadlock Risk
**Priority**: 🟠 HIGH | **Effort**: 4 hours | **Risk**: Medium

**Location**: `src/database/db_pool.py:85-136`

**Problem**: `_return_connection()` can hang during shutdown if database is locked.

**Solution**:
```python
def _return_connection(self, conn: sqlite3.Connection) -> None:
    with self._lock:
        if self._closed:
            self._safe_close_connection(conn)
            return
        is_closed = self._closed  # Capture state under lock

    if is_closed:
        self._safe_close_connection(conn)
        return

    # Health check with timeout
    try:
        conn.execute("SELECT 1")
        # Use put with timeout to avoid blocking forever
        try:
            self._pool.put(conn, timeout=5.0)
        except queue.Full:
            self._safe_close_connection(conn)
    except sqlite3.Error:
        self._replace_broken_connection(conn)

def _safe_close_connection(self, conn: sqlite3.Connection) -> None:
    """Close connection with timeout protection."""
    try:
        conn.close()
    except sqlite3.Error:
        pass

def close(self) -> None:
    """Close pool with timeout to prevent indefinite wait."""
    with self._lock:
        self._closed = True

    # Drain pool with timeout
    deadline = time.time() + 10.0  # 10 second max wait
    while time.time() < deadline:
        try:
            conn = self._pool.get_nowait()
            self._safe_close_connection(conn)
        except queue.Empty:
            break
```

**Acceptance Criteria**:
- [ ] Shutdown completes within 10 seconds even with active queries
- [ ] No deadlocks in stress test (100 concurrent operations + shutdown)
- [ ] Connections properly released on normal shutdown

---

### Task 2.2: Add Processing Queue Deduplication
**Priority**: 🟠 HIGH | **Effort**: 6 hours | **Risk**: Medium

**Location**: `src/processing/processing_queue.py:197-223, 483-503`

**Problem**: Retry mechanism can cause duplicate processing; no deduplication on restart.

**Solution**:
```python
class ProcessingQueue:
    def __init__(self, ...):
        self._processing_tasks: Dict[str, str] = {}  # task_id -> status
        self._task_lock = threading.Lock()

    def add_recording(self, recording_data: Dict) -> Optional[str]:
        recording_id = recording_data.get('recording_id')

        with self._task_lock:
            # Check for existing task for this recording
            existing = self._find_task_for_recording(recording_id)
            if existing and existing['status'] in ('pending', 'processing'):
                logger.warning(f"Recording {recording_id} already queued as {existing['task_id']}")
                return None

            task_id = str(uuid.uuid4())
            # ... create task ...

        return task_id

    def _retry_task(self, task_id: str, recording_data: Dict, error_msg: str):
        with self._task_lock:
            # Mark original task as "retrying" to prevent duplicates
            self._processing_tasks[task_id] = 'retrying'

            # Create NEW task ID for retry
            new_task_id = f"{task_id}_retry_{retry_count}"
            recording_data['original_task_id'] = task_id
            recording_data['task_id'] = new_task_id

        # ... schedule retry with new ID ...

    def _recover_incomplete_tasks(self):
        """Called on startup to handle tasks left in 'processing' state."""
        incomplete = self.db.get_incomplete_tasks()
        for task in incomplete:
            if task['status'] == 'processing':
                # Reset to pending for retry
                self.db.update_task_status(task['id'], 'pending')
                self.add_recording(task['data'])
```

**Acceptance Criteria**:
- [ ] Same recording cannot be queued twice
- [ ] Retry creates new task ID, preserves original reference
- [ ] Crash recovery doesn't duplicate tasks
- [ ] Database shows clear task lineage

---

### Task 2.3: Protect User Edits from Background Updates
**Priority**: 🟠 HIGH | **Effort**: 4 hours | **Risk**: Low

**Location**: `src/core/app_initializer.py:456-497`

**Problem**: Background queue updates can overwrite user's manual edits.

**Solution**:
```python
class MedicalDictationApp:
    def __init__(self):
        self._content_modified = {
            'transcript': False,
            'soap': False,
            'referral': False,
            'letter': False
        }
        self._current_recording_id: Optional[int] = None

    def _on_text_modified(self, tab_name: str):
        """Called when user edits text in any tab."""
        self._content_modified[tab_name] = True

    def _can_update_tab(self, tab_name: str, recording_id: int) -> bool:
        """Check if safe to update tab with background results."""
        # Always safe if empty
        if not self._get_tab_content(tab_name).strip():
            return True

        # Safe if same recording and not modified
        if (self._current_recording_id == recording_id and
            not self._content_modified[tab_name]):
            return True

        return False

    def _update_ui_with_results(self, recording_id: int, ...):
        for tab_name, content in [('transcript', transcript), ('soap', soap_note)]:
            if self._can_update_tab(tab_name, recording_id):
                self._set_tab_content(tab_name, content)
                self._content_modified[tab_name] = False
            else:
                # Queue notification instead of overwriting
                self._notify_results_available(recording_id, tab_name)
```

**Acceptance Criteria**:
- [ ] User edits are never overwritten without confirmation
- [ ] Background results stored and accessible via notification
- [ ] Modified indicator shown in UI (optional)
- [ ] Clear workflow for reviewing queued results

---

## Sprint 3: Code Quality & Maintainability (Backlog)

### Task 3.1: Refactor Controllers to Use Dependency Injection
**Priority**: 🟡 MEDIUM | **Effort**: 2-3 days | **Risk**: Medium

**Location**: All controllers in `src/core/`

**Problem**: Controllers access `self.app.*` freely, creating tight coupling.

**Solution**: Define explicit interfaces
```python
# src/core/interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol

class StatusManagerProtocol(Protocol):
    def info(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def success(self, message: str) -> None: ...

class RecordingManagerProtocol(Protocol):
    @property
    def is_recording(self) -> bool: ...
    def start_recording(self, callback: Callable) -> bool: ...
    def stop_recording(self) -> None: ...

# src/core/recording_controller.py
class RecordingController:
    def __init__(
        self,
        recording_manager: RecordingManagerProtocol,
        status_manager: StatusManagerProtocol,
        audio_handler: AudioHandler,
        ui_updater: Callable[[bool, str], None]
    ):
        self._recording_manager = recording_manager
        self._status_manager = status_manager
        self._audio_handler = audio_handler
        self._update_ui = ui_updater
```

**Acceptance Criteria**:
- [ ] Controllers don't reference `self.app`
- [ ] Dependencies explicitly declared in constructor
- [ ] Unit tests can mock dependencies
- [ ] No circular imports

---

### Task 3.2: Standardize Error Handling
**Priority**: 🟡 MEDIUM | **Effort**: 2 days | **Risk**: Low

**Location**: `src/audio/audio.py:354-490` and throughout codebase

**Problem**: Inconsistent error handling, silent failures, no error differentiation.

**Solution**:
```python
# src/errors.py
class MedicalAssistantError(Exception):
    """Base exception for all application errors."""
    pass

class AudioError(MedicalAssistantError):
    """Audio processing errors."""
    pass

class TranscriptionError(AudioError):
    """Transcription-specific errors."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable

class AudioFormatError(AudioError):
    """Unsupported audio format."""
    def __init__(self, message: str, supported_formats: List[str]):
        super().__init__(message)
        self.supported_formats = supported_formats

# Usage in audio.py
def process_audio_data(self, audio_data) -> Tuple[AudioSegment, str]:
    try:
        # ... processing ...
        return segment, transcript
    except sr.UnknownValueError:
        raise TranscriptionError("Could not understand audio", retryable=False)
    except sr.RequestError as e:
        raise TranscriptionError(f"API error: {e}", retryable=True)
    except Exception as e:
        raise AudioError(f"Processing failed: {e}")
```

**Acceptance Criteria**:
- [ ] All errors inherit from `MedicalAssistantError`
- [ ] Errors indicate retryability
- [ ] UI displays actionable error messages
- [ ] Logging includes error type and context

---

### Task 3.3: Break Up AppInitializer
**Priority**: 🟡 MEDIUM | **Effort**: 1-2 days | **Risk**: Low

**Location**: `src/core/app_initializer.py`

**Problem**: 500-line class handling threading, UI, security, audio, database, etc.

**Solution**:
```python
# src/core/setup/
#   __init__.py
#   threading_setup.py
#   ui_setup.py
#   security_setup.py
#   audio_setup.py
#   database_setup.py

# src/core/app_initializer.py
class AppInitializer:
    """Orchestrates initialization using specialized setup classes."""

    def __init__(self, app: 'MedicalDictationApp'):
        self.app = app
        self._setups = [
            ThreadingSetup(app),
            SecuritySetup(app),
            DatabaseSetup(app),
            AudioSetup(app),
            UISetup(app),
        ]

    def initialize_application(self):
        for setup in self._setups:
            setup.initialize()

        self._finalize()
```

**Acceptance Criteria**:
- [ ] Each setup class < 100 lines
- [ ] Clear dependency order between setups
- [ ] Easy to add new setup phases
- [ ] AppInitializer < 100 lines

---

## Summary

| Sprint | Tasks | Total Effort | Focus |
|--------|-------|--------------|-------|
| **Sprint 1** | 4 critical fixes | ~7.5 hours | Security & Stability |
| **Sprint 2** | 3 high-priority fixes | ~14 hours | Reliability & Data Integrity |
| **Sprint 3** | 3 code quality improvements | ~5-7 days | Maintainability |

### Recommended Order

1. **Task 1.1** (SQL Injection) - Quick win, high impact
2. **Task 1.3** (Race Condition) - User-visible bugs
3. **Task 1.4** (Audio Leak) - Device availability issues
4. **Task 1.2** (Memory Leak) - Long-running stability
5. **Task 2.1** (Deadlock) - Shutdown reliability
6. **Task 2.2** (Deduplication) - Data integrity
7. **Task 2.3** (Edit Protection) - User experience
8. **Tasks 3.x** - As time permits

---

## Testing Strategy

Each task should include:
1. **Unit tests** for the specific fix
2. **Integration test** verifying the fix doesn't break existing functionality
3. **Manual test** for user-facing changes

### Critical Path Tests
- [ ] App starts successfully
- [ ] Recording start/stop/pause works
- [ ] Queue processing completes
- [ ] Shutdown is clean (no hangs)
- [ ] No "device busy" errors on restart
