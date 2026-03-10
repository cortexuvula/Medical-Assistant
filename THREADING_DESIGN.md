# Threading Design Document

This document describes the threading architecture of the Medical Assistant application,
including all synchronization primitives, thread lifecycles, lock ordering conventions,
and shutdown coordination.

---

## 1. Lock Inventory

All locks, their types, locations, and purposes.

### Core Application Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `ProcessingQueue.lock` | `RLock` | `src/processing/processing_queue.py:145` | Protects all shared queue state: task dicts, batch tracking, deduplication maps. Acquired in 31 sites across 4 mixins. |
| `RecordingController._state_lock` | `Lock` | `src/core/controllers/recording_controller.py:72` | Guards recording state transitions (start/stop/pause/resume). Shared with `PauseResumeHandler`. |
| `AudioStateManager._lock` | `Lock` | `src/audio/audio_state_manager.py:49` | Protects audio segment lists, recording state enum, memory tracking, and format parameters. |
| `AudioHandler._streams_lock` | `Lock` (class-level) | `src/audio/audio.py:71` | Guards the class-level `_active_streams` dict for thread-safe stream lifecycle management. |
| `SOAPAudioProcessor._callback_count_lock` | `Lock` (class-level) | `src/audio/soap_audio_processor.py:32` | Serializes access to the audio callback counter for periodic logging. |
| `RecordingAutoSaveManager._lock` | `Lock` | `src/audio/recording_autosave_manager.py:59` | Protects autosave session state, chunk tracking, and metadata. |
| `PeriodicAnalyzer._lock` | `Lock` | `src/audio/periodic_analysis.py:41` | Guards timer state, analysis count, history list, and callback references. |

### Database Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `ConnectionPool._lock` | `RLock` | `src/database/db_pool.py:51` | Protects `_all_connections` list and `_closed` flag. Never held during queue waits. |
| `ConnectionPool._lock` (singleton) | `Lock` | `src/database/db_pool.py:307` | Double-checked locking for the connection pool singleton. |
| `Database._lock` | `Lock` | `src/database/database.py:130` | Protects `_thread_connections` dict and `_closed` flag for thread-local connection management. |
| `Database._instances_lock` | `Lock` (class-level) | `src/database/database.py:118` | Guards the class-level `_instances` list for global cleanup registration. |

### Settings and Configuration Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `_settings_cache_lock` | `Lock` (module-level) | `src/settings/settings.py:31` | Protects the in-memory settings cache and its TTL timestamp. |
| `ModelProvider (LRUCache)._lock` | `RLock` | `src/ai/model_provider.py:60` | Thread-safe LRU cache for fetched model lists with TTL expiry. |

### Manager Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `AutoSaveManager._providers_lock` | `RLock` | `src/managers/autosave_manager.py:61` | Protects `_data_providers` dict. Must be acquired before `_state_lock`. |
| `AutoSaveManager._state_lock` | `RLock` | `src/managers/autosave_manager.py:62` | Protects save state (`_is_running`, `last_save_time`, `last_data_hash`). |
| `VocabularyManager._instance_lock` | `Lock` (class-level) | `src/managers/vocabulary_manager.py:37` | Singleton double-checked locking. |
| `TranslationSessionManager._lock` | `Lock` (class-level) | `src/managers/translation_session_manager.py:27` | Singleton double-checked locking. |
| `_translation_manager_lock` | `Lock` (module-level) | `src/managers/translation_manager.py:351` | Singleton guard for `TranslationManager`. |
| `_tts_manager_lock` | `Lock` (module-level) | `src/managers/tts_manager.py:435` | Singleton guard for `TTSManager`. |
| `BaseProviderManager._lock` | `Lock` (class-level) | `src/managers/base_provider_manager.py:311` | Singleton guard for provider manager instances. |
| `_manager_lock` | `Lock` (module-level) | `src/managers/translation_session_manager.py:424` | Singleton guard for translation session manager. |
| `RagUploadQueue._lock` | `Lock` | `src/managers/rag_upload_queue.py:170` | Protects the upload queue state and executor reference. |
| `RagDocumentManager._processing_lock` | `Lock` | `src/managers/rag_document_manager.py:64` | Serializes document processing to prevent concurrent uploads. |
| `NotificationManager` (implicit) | Queue-based | `src/managers/notification_manager.py:38` | Uses `queue.Queue` for thread-safe notification dispatch. |

### Utility Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `ThreadRegistry._lock` | `Lock` | `src/utils/thread_registry.py:29` | Protects the `WeakSet` of tracked threads and the names dict. |
| `ThreadRegistry._init_lock` | `Lock` (class-level) | `src/utils/thread_registry.py:22` | Singleton double-checked locking. |
| `ThreadPoolManager._lock` | `Lock` (class-level) | `src/utils/thread_pool.py:58` | Singleton guard for the shared `ThreadPoolExecutor`. |
| `CircuitBreaker._lock` | `Lock` | `src/utils/resilience.py:304` | Protects failure count, state transitions, and last failure time. |
| `TempFileTracker._lock` | `Lock` (class-level) | `src/utils/temp_file_tracker.py:21` | Singleton double-checked locking. |
| `TempFileTracker._files_lock` | `Lock` | `src/utils/temp_file_tracker.py:25` | Protects the set of tracked temporary file paths. |
| `AuditLogger._lock` | `Lock` (class-level) | `src/utils/audit_logger.py:97` | Singleton double-checked locking. |
| `AuditLogger._write_lock` | `Lock` | `src/utils/audit_logger.py:114` | Serializes writes to the append-only audit log file. |
| `HttpClientManager._lock` | `Lock` (class-level) | `src/utils/http_client_manager.py:34` | Singleton guard. |
| `HttpClientManager._client_lock` | `Lock` | `src/utils/http_client_manager.py:66` | Protects per-provider connection pool creation. |
| `StructuredLogger._context_lock` | `Lock` | `src/utils/structured_logging.py:220` | Protects thread-local logging context. |
| `_loggers_lock` | `Lock` (module-level) | `src/utils/structured_logging.py:367` | Guards the global logger registry dict. |
| `StructuredLogger._counter_lock` | `Lock` | `src/utils/structured_logging.py:503` | Protects log-rate-limiting counters. |
| `HealthChecker._lock` | `Lock` (class-level) | `src/utils/health_checker.py:356` | Singleton guard. |
| `HealthChecker._cache_lock` | `Lock` | `src/utils/health_checker.py:379` | Protects cached health check results. |
| `_health_checker_lock` | `Lock` (module-level) | `src/utils/health_checker.py:558` | Module-level singleton guard. |
| `_refiner_lock` | `Lock` (module-level) | `src/ai/translation_refiner.py:206` | Singleton guard for the translation refiner. |

### RAG / Knowledge Graph Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `_worker_lock` | `Lock` (module-level) | `src/rag/graphiti_client.py:142` | Singleton guard for the Graphiti event loop worker. |
| `GraphitiClientWrapper._init_lock` | `Lock` | `src/rag/graphiti_client.py:196` | Protects lazy initialization of the Graphiti client. |
| `_guidelines_worker_lock` | `Lock` (module-level) | `src/rag/guidelines_graphiti_client.py:119` | Singleton guard for the guidelines Graphiti worker. |
| `GuidelinesGraphitiWrapper._init_lock` | `Lock` | `src/rag/guidelines_graphiti_client.py:173` | Lazy init guard for guidelines Graphiti client. |
| `_guidelines_store_lock` | `Lock` (module-level) | `src/rag/guidelines_vector_store.py:996` | Singleton guard for the guidelines vector store. |
| `GuidelinesVectorStore._pool_lock` | `Lock` | `src/rag/guidelines_vector_store.py:53` | Protects the async connection pool reference. |
| `GuidelinesUploadManager._processing_lock` | `Lock` | `src/rag/guidelines_upload_manager.py:60` | Serializes guideline upload processing. |
| `_guidelines_upload_manager_lock` | `Lock` (module-level) | `src/rag/guidelines_upload_manager.py:710` | Singleton guard. |
| `StreamingSearchState._lock` | `Lock` | `src/rag/streaming_models.py:78` | Protects streaming search state during parallel retrieval. |
| `FallbackCacheProvider._lock` | `Lock` | `src/rag/cache/fallback_provider.py:47` | Protects in-memory fallback cache. |
| `SqliteCacheProvider._lock` | `Lock` | `src/rag/cache/sqlite_provider.py:42` | Serializes SQLite cache operations. |
| `RAGHealthManager._lock` | `Lock` | `src/rag/health_manager.py:98` | Protects RAG health status state. |

### MCP (Model Context Protocol) Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `rate_limit_lock` | `Lock` (module-level) | `src/ai/mcp/mcp_tool_wrapper.py:27` | Global rate limiter for MCP tool invocations. |
| `MCPToolWrapper._lock` | `Lock` | `src/ai/mcp/mcp_tool_wrapper.py:44` | Protects per-wrapper tool call state. |
| `MCPManager._lock` | `Lock` | `src/ai/mcp/mcp_manager.py:192` | Protects MCP server registry and lifecycle state. |

### Other Locks

| Lock | Type | File:Line | Purpose |
|------|------|-----------|---------|
| `PyttsxProvider._lock` | `Lock` | `src/tts_providers/pyttsx_provider.py:52` | Serializes access to the pyttsx3 engine (not thread-safe). |
| `RateLimiter` (save_thread) | `Lock` (implicit) | `src/utils/security/rate_limiter.py:258` | Rate limit state persistence uses daemon save thread. |

### Threading Events

| Event | File:Line | Purpose |
|-------|-----------|---------|
| `AudioHandler (stream_started)` | `src/audio/audio.py:1112` | Signals that PortAudio stream has started on background thread. |
| `RecordingAutoSaveManager._stop_event` | `src/audio/recording_autosave_manager.py:60` | Clean shutdown signal for autosave thread. |
| `RecordingAutoSaveManager._save_complete` | `src/audio/recording_autosave_manager.py:61` | Signals save completion for synchronization. |
| `PeriodicAnalyzer._stop_event` | `src/audio/periodic_analysis.py:42` | Clean shutdown signal for analysis timer. |
| `PeriodicAnalyzer._callback_complete` | `src/audio/periodic_analysis.py:43` | Signals when analysis callback finishes. |
| `AutoSaveManager._stop_event` | `src/managers/autosave_manager.py:63` | Clean shutdown signal for autosave loop. |
| `GraphitiWorker._started` | `src/rag/graphiti_client.py:85` | Signals event loop is ready to accept work. |
| `GuidelinesGraphitiWorker._started` | `src/rag/guidelines_graphiti_client.py:72` | Signals guidelines event loop is ready. |
| `CancellationToken._cancelled` | `src/rag/streaming_models.py:76` | Cooperative cancellation for streaming RAG searches. |

---

## 2. Lock Ordering Hierarchy

Locks are organized into four tiers. When multiple locks must be held simultaneously,
they **must** be acquired in tier order (L1 before L2 before L3 before L4). Locks within
the same tier should never be held simultaneously unless explicitly documented.

### L1 -- Outermost (Application-Level State)

| Lock | Rationale |
|------|-----------|
| `ProcessingQueue.lock` | Coordinates task state across 4 mixins (batch, reprocessing, guidelines, core queue). 31 acquisition sites. |
| `RecordingController._state_lock` | Guards all recording state transitions; shared with `PauseResumeHandler`. |
| `AutoSaveManager._providers_lock` | Must be acquired before `_state_lock` per class documentation. |

### L2 -- Mid-Level (Subsystem State)

| Lock | Rationale |
|------|-----------|
| `AudioStateManager._lock` | Protects audio buffers; acquired inside recording operations that may hold L1. |
| `AudioHandler._streams_lock` | Class-level lock for stream lifecycle; may be acquired after recording state lock. |
| `AutoSaveManager._state_lock` | Always acquired after `_providers_lock` (L1). |
| `PeriodicAnalyzer._lock` | Guards timer state; started/stopped from recording controller (L1). |
| `RecordingAutoSaveManager._lock` | Manages autosave sessions; controlled by recording lifecycle (L1). |
| `MCPManager._lock` | Protects MCP server registry; independent subsystem. |

### L3 -- Resource Pools and Caches

| Lock | Rationale |
|------|-----------|
| `ConnectionPool._lock` | Pool-level state; never held during queue waits per documentation. |
| `HttpClientManager._client_lock` | Per-provider HTTP pool creation; short hold times. |
| `LRUCache._lock` (ModelProvider) | Model list cache; acquired during API calls that may use L1/L2 callers. |
| `GuidelinesVectorStore._pool_lock` | Async connection pool reference guard. |
| `RagUploadQueue._lock` | Upload queue state; independent of processing queue. |
| `StreamingSearchState._lock` | Streaming search progress; short-lived. |

### L4 -- Innermost (Fine-Grained / Leaf Locks)

| Lock | Rationale |
|------|-----------|
| `Database._lock` | Thread-local connection tracking; minimal contention. |
| `Database._instances_lock` | Class-level instance registry; acquired only at init/shutdown. |
| `CircuitBreaker._lock` | Per-breaker state; leaf lock with no further acquisitions. |
| `ThreadRegistry._lock` | Thread tracking; acquired briefly at register/shutdown. |
| `TempFileTracker._files_lock` | File path set; leaf lock. |
| `AuditLogger._write_lock` | Append-only log writes; no further locks needed. |
| `_settings_cache_lock` | Settings cache TTL check; very short hold time. |
| `StructuredLogger._context_lock` | Logging context; must never call into application code. |
| `_loggers_lock` | Logger registry; module-level, no nested acquisitions. |
| `SOAPAudioProcessor._callback_count_lock` | Simple counter; leaf lock. |
| All singleton `_init_lock` / module-level `_*_lock` guards | Double-checked locking pattern; held only during first initialization. |

---

## 3. Thread Lifecycle

### Long-Running Background Threads

| Thread | Created In | Daemon | Purpose | Shutdown Mechanism |
|--------|-----------|--------|---------|-------------------|
| `ProcessingQueue.processor_thread` | `processing_queue.py:169` | Yes | Drains the task queue and dispatches to executor | `shutdown()` sets `_running=False`, puts poison pill on queue |
| `ProcessingQueue.executor` (pool) | `processing_queue.py:126` | Implicit | `ThreadPoolExecutor(max_workers)` for concurrent task processing | `executor.shutdown(wait=True)` |
| `ProcessingQueue.guideline_executor` (pool) | `processing_queue.py:129` | Implicit | Dedicated `ThreadPoolExecutor` for guideline uploads | `executor.shutdown(wait=True)` |
| `AutoSaveManager.save_thread` | `autosave_manager.py:141` | Yes | Periodic save loop checking data providers | `_stop_event.set()` wakes the loop |
| `PeriodicAnalyzer._countdown_thread` | `periodic_analysis.py:277` | Yes | Countdown timer for next analysis interval | `_stop_event.set()` breaks countdown sleep |
| `RecordingAutoSaveManager._save_thread` | `recording_autosave_manager.py:153` | Yes | Incremental audio chunk saving during recording | `_stop_event.set()` |
| `RecordingManager.recording_thread` | `recording_manager.py:100` | Yes | Audio capture callback loop | Recording stop sets flag, thread exits |
| `NotificationManager.processor_thread` | `notification_manager.py:38` | Yes | Processes notification queue for UI display | `cleanup()` stops the thread |
| `GraphitiWorker._thread` | `graphiti_client.py:93` | Yes | asyncio event loop for Neo4j/Graphiti operations | Event loop shutdown |
| `GuidelinesGraphitiWorker._thread` | `guidelines_graphiti_client.py:80` | Yes | asyncio event loop for guidelines Graphiti | Event loop shutdown |
| `MCP reader_thread` | `mcp_manager.py:82` | Yes | Reads JSON-RPC responses from MCP server stdout | Server process termination |
| `MCP stderr_thread` | `mcp_manager.py:85` | Yes | Reads MCP server stderr for logging | Server process termination |
| `MCP HealthMonitor._thread` | `mcp_manager.py:440` | Yes | Periodic health checks on MCP servers | Monitor loop flag |
| `ChatProcessor thread` | `chat_processor.py:122` | Yes | Streaming chat response processing | Completes naturally per request |

### Application-Level Executor Pools

| Pool | Created In | Max Workers | Purpose |
|------|-----------|-------------|---------|
| `app.io_executor` | `app_initializer.py:89` | `min(32, cpu_count * 4)` | General I/O-bound tasks (network, file ops) |
| `app.executor` | `core/setup/threading_setup.py:32` | Configurable | Application-level task executor |
| `ThreadPoolManager._executor` | `utils/thread_pool.py:77` | 4 (default) | Centralized shared pool for ad-hoc background work |
| `StreamingHybridRetriever._executor` | `rag/streaming_retriever.py:74` | Configurable | Parallel vector/BM25/graph search execution |
| `RagUploadQueue._executor` | `managers/rag_upload_queue.py:163` | Configurable | Non-blocking RAG document uploads |
| `ToolExecutor._executor` | `ai/tools/tool_executor.py:30` | 3 | MCP/agent tool execution with timeouts |

### Short-Lived / Fire-and-Forget Daemon Threads

These threads are spawned for specific one-off operations and complete naturally:

| Spawn Site | Purpose |
|-----------|---------|
| `core/handlers/periodic_analysis_handler.py:208` | Single analysis run during recording |
| `core/app_initializer.py:678` | Background RAG sync on startup |
| `core/app_initializer.py:726` | Background guidelines refresh on startup |
| `ui/dialogs/tts_settings_dialog.py:220` | Fetch ElevenLabs voices list |
| `ui/dialogs/knowledge_graph_dialog.py:375` | Load graph data from Neo4j |
| `ui/dialogs/recordings_dialog_manager.py:230,543` | Background export/import tasks |
| `ui/dialogs/translation/*.py` | Translation, TTS synthesis, recording operations |
| `ui/components/recordings_tab_data.py:87` | Async data loading for recordings list |
| `ui/components/recordings_tab_events.py:280` | Background event processing |
| `ui/components/notebook_tabs.py:850,906` | Guideline upload and file processing |
| `ui/loading_indicator.py:290` | Background task with loading spinner |
| `ui/dialogs/rsvp/input_mode.py:265` | PDF text extraction |
| `ui/dialogs/guidelines_library_dialog.py:237,431` | Fetch guidelines/chunks from store |
| `processing/reprocessing_mixin.py:199` | Delayed task requeue after failure |
| `core/mixins/app_recording_mixin.py:181` | Cancel recording task |
| `managers/rag_document_manager.py:244,437` | Graph ingestion threads |
| `managers/tts_manager.py:263` | Audio playback thread |
| `utils/security/rate_limiter.py:258` | Async rate limit state persistence |
| `utils/error_handling.py:1055` | Generic `run_in_background()` helper |

---

## 4. Deadlock Avoidance Rules

### Rule 1: Never Hold a Lock During I/O or External Waits

Release locks before performing network calls, file I/O, database queries, or waiting
on `threading.Event`. The `ProcessingQueue` follows this pattern: acquire `self.lock`
to read/update task state, release it, then perform the actual processing work.

**Anti-pattern:**
```python
with self.lock:
    result = api_client.call(...)  # WRONG: holds lock during network I/O
    self.state = result
```

**Correct pattern:**
```python
with self.lock:
    task = self.pending_tasks[task_id]
# Lock released before I/O
result = api_client.call(task)
with self.lock:
    self.state = result
```

### Rule 2: Acquire Locks in Hierarchy Order

When multiple locks must be held, always acquire in L1 -> L2 -> L3 -> L4 order.
Never acquire an outer-tier lock while holding an inner-tier lock.

The `AutoSaveManager` documents this explicitly: `_providers_lock` (L1) must be
acquired before `_state_lock` (L2).

### Rule 3: Use Timeouts on Blocking Operations

- `ConnectionPool` uses `CLOSE_TIMEOUT = 10.0` and `HEALTH_CHECK_TIMEOUT = 1.0`
- `ThreadRegistry.shutdown()` uses a `timeout` parameter (default 10s) with per-thread budget
- `queue.Queue.get(timeout=...)` is preferred over indefinite blocking
- `threading.Event.wait(timeout=...)` should always specify a timeout in shutdown paths

### Rule 4: Use Daemon Threads for Background Work

All background threads are created with `daemon=True` to prevent blocking application
exit if shutdown coordination fails. This is a safety net -- orderly shutdown via
Events and flags is still preferred.

### Rule 5: Use `safe_ui_update()` for Cross-Thread UI Updates

Never call tkinter methods directly from a worker thread. Use one of:

- `schedule_ui_update(widget, callback)` from `src/utils/safe_ui.py` -- checks
  `winfo_exists()` before invoking the callback via `widget.after(0, ...)`
- `safe_ui_update(app, callback)` from `src/utils/error_handling.py` -- similar
  pattern used in the `run_in_background()` helper
- `app.parent.after(0, lambda: ...)` -- direct scheduling (must manually check
  widget existence)

All three patterns marshal the callback onto the main thread's event loop, avoiding
`RuntimeError: main thread is not in main loop` crashes.

---

## 5. High-Contention Areas

### ProcessingQueue.lock (31 acquisition sites across 4 mixins)

This is the most contended lock in the application, used by:

| File | Sites | Operations |
|------|-------|------------|
| `processing_queue.py` | 13 | Queue, dequeue, status updates, deduplication, retry, cancel, shutdown |
| `guidelines_processing_mixin.py` | 11 | Batch create, update, complete, cancel, progress tracking |
| `batch_processing_mixin.py` | 6 | Batch initiation, per-item status, completion |
| `reprocessing_mixin.py` | 1 | Delayed requeue |

**Mitigation:** The lock is an `RLock`, allowing recursive acquisition within the same
thread. Critical sections are kept short (dict lookups and assignments). Actual
processing (AI calls, transcription, file I/O) happens outside the lock.

### ConnectionPool._lock

Acquired on every `acquire()` and `release()` for connection health checks and the
`_all_connections` list. Mitigated by:
- Using `queue.Queue` for the actual pool (inherently thread-safe for get/put)
- Short hold times (only for metadata updates)
- Health check interval (`HEALTH_CHECK_INTERVAL = 300s`) to skip redundant checks

### Settings Cache Lock

`_settings_cache_lock` is acquired on every `load_settings()` call to check the TTL.
Mitigated by the 60-second cache TTL, which avoids repeated file reads.

### AudioHandler._streams_lock

Class-level lock acquired during stream start, stop, and cleanup. Contention is low
because stream operations are infrequent (typically one active stream at a time).

---

## 6. Shutdown Coordination

Shutdown is orchestrated by `WindowController.on_closing()` in
`src/core/controllers/window_controller.py:406`. The order is designed to stop
producers before consumers, and high-level components before low-level resources.

### Shutdown Sequence

```
1. Stop SOAP recording
   - Calls soap_stop_listening_function(True)
   - Waits 200ms for audio thread to release resources

2. Stop periodic analysis
   - Calls _stop_periodic_analysis()
   - Sets PeriodicAnalyzer._stop_event, which breaks the countdown loop

3. Clean up audio handler
   - Calls audio_handler.cleanup_resources()
   - Closes all active PortAudio streams via _streams_lock

4. Shutdown processing queue
   - Calls processing_queue.shutdown(wait=True)
   - Sets _running=False, puts poison pill on queue
   - Waits for processor_thread to drain
   - Shuts down ThreadPoolExecutor (wait=True)

5. Shutdown thread registry
   - ThreadRegistry.instance().shutdown(timeout=5.0)
   - Joins all registered I/O threads with per-thread timeout budget

6. Clean up temp files
   - TempFileTracker.instance().cleanup_all()
   - Removes any tracked temporary files (PHI safety)

7. Clean up notification manager
   - notification_manager.cleanup()
   - Stops the notification processor thread

8. Stop MCP servers
   - mcp_manager.stop_all()
   - Terminates all MCP server subprocesses
   - Reader and stderr threads exit when pipes close

9. Shutdown executor pools
   - app.io_executor.shutdown(wait=True, cancel_futures=True)
   - app.executor.shutdown(wait=True, cancel_futures=True)

10. Destroy window
    - app.destroy()
    - Terminates the tkinter main loop
```

### Shutdown Safety Properties

- **Daemon threads as safety net:** All background threads are daemon threads. If orderly
  shutdown fails or hangs, the process will still exit when the main thread terminates.
- **Timeout budgets:** `ThreadRegistry.shutdown()` divides its timeout across all active
  threads, ensuring shutdown does not hang indefinitely.
- **Error isolation:** Each shutdown step is wrapped in `try/except` so that failure in
  one component does not prevent cleanup of others.
- **No lock held across steps:** The shutdown sequence does not hold any application lock
  while iterating through the steps, avoiding deadlock with worker threads that may be
  waiting for those locks.
- **`winfo_exists()` guards:** Worker threads that attempt UI updates after window
  destruction are silently dropped by `safe_ui_update()` / `schedule_ui_update()`.
