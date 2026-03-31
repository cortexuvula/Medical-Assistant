"""
Tests for src/managers/rag_upload_queue.py

Covers UploadTaskStatus enum, UploadTask dataclass (fields, defaults),
UploadSession dataclass (fields, properties: total_tasks, completed_tasks,
failed_tasks, cancelled_tasks, progress_percent, is_complete),
and UploadProgressUpdate dataclass.
No network, no file I/O, no actual uploads.
"""

import sys
import pytest
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from managers.rag_upload_queue import (
    UploadTaskStatus,
    UploadTask,
    UploadSession,
    UploadProgressUpdate,
    RAGUploadQueueManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(status=UploadTaskStatus.QUEUED, progress=0.0) -> UploadTask:
    t = UploadTask(task_id="t1", session_id="s1", file_path="/tmp/test.pdf")
    t.status = status
    t.progress_percent = progress
    return t


def _session(tasks=None) -> UploadSession:
    s = UploadSession(session_id="sess1")
    if tasks:
        s.tasks = tasks
    return s


# ===========================================================================
# UploadTaskStatus enum
# ===========================================================================

class TestUploadTaskStatus:
    def test_has_queued(self):
        assert UploadTaskStatus.QUEUED is not None

    def test_has_extracting(self):
        assert UploadTaskStatus.EXTRACTING is not None

    def test_has_chunking(self):
        assert UploadTaskStatus.CHUNKING is not None

    def test_has_embedding(self):
        assert UploadTaskStatus.EMBEDDING is not None

    def test_has_syncing(self):
        assert UploadTaskStatus.SYNCING is not None

    def test_has_completed(self):
        assert UploadTaskStatus.COMPLETED is not None

    def test_has_failed(self):
        assert UploadTaskStatus.FAILED is not None

    def test_has_cancelled(self):
        assert UploadTaskStatus.CANCELLED is not None

    def test_values_are_strings(self):
        for member in UploadTaskStatus:
            assert isinstance(member.value, str)

    def test_has_eight_members(self):
        assert len(UploadTaskStatus) == 8

    def test_queued_value(self):
        assert UploadTaskStatus.QUEUED.value == "queued"

    def test_completed_value(self):
        assert UploadTaskStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert UploadTaskStatus.FAILED.value == "failed"

    def test_cancelled_value(self):
        assert UploadTaskStatus.CANCELLED.value == "cancelled"


# ===========================================================================
# UploadTask dataclass
# ===========================================================================

class TestUploadTask:
    def test_required_fields_stored(self):
        t = UploadTask(task_id="tid", session_id="sid", file_path="/tmp/file.pdf")
        assert t.task_id == "tid"
        assert t.session_id == "sid"
        assert t.file_path == "/tmp/file.pdf"

    def test_default_status_is_queued(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.status == UploadTaskStatus.QUEUED

    def test_default_progress_is_zero(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.progress_percent == pytest.approx(0.0)

    def test_default_error_message_is_none(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.error_message is None

    def test_default_document_id_is_none(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.document_id is None

    def test_default_started_at_is_none(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.started_at is None

    def test_default_completed_at_is_none(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.completed_at is None

    def test_created_at_is_datetime(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert isinstance(t.created_at, datetime)

    def test_created_at_is_recent(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        delta = (datetime.now() - t.created_at).total_seconds()
        assert delta < 5

    def test_default_options_is_empty_dict(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        assert t.options == {}

    def test_instances_dont_share_options(self):
        t1 = UploadTask(task_id="t1", session_id="s", file_path="/f")
        t2 = UploadTask(task_id="t2", session_id="s", file_path="/f")
        t1.options["key"] = "val"
        assert t2.options == {}

    def test_status_can_be_changed(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        t.status = UploadTaskStatus.COMPLETED
        assert t.status == UploadTaskStatus.COMPLETED

    def test_progress_can_be_set(self):
        t = UploadTask(task_id="t", session_id="s", file_path="/f")
        t.progress_percent = 55.0
        assert t.progress_percent == pytest.approx(55.0)


# ===========================================================================
# UploadSession dataclass — fields
# ===========================================================================

class TestUploadSessionFields:
    def test_session_id_stored(self):
        s = UploadSession(session_id="my-session")
        assert s.session_id == "my-session"

    def test_default_tasks_is_empty_list(self):
        s = UploadSession(session_id="s")
        assert s.tasks == []

    def test_default_options_is_empty_dict(self):
        s = UploadSession(session_id="s")
        assert s.options == {}

    def test_created_at_is_datetime(self):
        s = UploadSession(session_id="s")
        assert isinstance(s.created_at, datetime)

    def test_cancellation_token_created(self):
        s = UploadSession(session_id="s")
        assert s.cancellation_token is not None

    def test_instances_dont_share_tasks(self):
        s1 = UploadSession(session_id="s1")
        s2 = UploadSession(session_id="s2")
        s1.tasks.append(_task())
        assert s2.tasks == []


# ===========================================================================
# UploadSession — total_tasks property
# ===========================================================================

class TestUploadSessionTotalTasks:
    def test_empty_session_has_zero_total(self):
        assert _session().total_tasks == 0

    def test_single_task_total_is_one(self):
        assert _session([_task()]).total_tasks == 1

    def test_multiple_tasks_counted(self):
        tasks = [_task() for _ in range(5)]
        assert _session(tasks).total_tasks == 5


# ===========================================================================
# UploadSession — completed_tasks property
# ===========================================================================

class TestUploadSessionCompletedTasks:
    def test_no_completed_returns_zero(self):
        tasks = [_task(UploadTaskStatus.QUEUED), _task(UploadTaskStatus.FAILED)]
        assert _session(tasks).completed_tasks == 0

    def test_one_completed_counted(self):
        tasks = [_task(UploadTaskStatus.COMPLETED), _task(UploadTaskStatus.QUEUED)]
        assert _session(tasks).completed_tasks == 1

    def test_all_completed_counted(self):
        tasks = [_task(UploadTaskStatus.COMPLETED) for _ in range(3)]
        assert _session(tasks).completed_tasks == 3


# ===========================================================================
# UploadSession — failed_tasks property
# ===========================================================================

class TestUploadSessionFailedTasks:
    def test_no_failed_returns_zero(self):
        tasks = [_task(UploadTaskStatus.COMPLETED)]
        assert _session(tasks).failed_tasks == 0

    def test_one_failed_counted(self):
        tasks = [_task(UploadTaskStatus.FAILED), _task(UploadTaskStatus.COMPLETED)]
        assert _session(tasks).failed_tasks == 1

    def test_multiple_failed_counted(self):
        tasks = [_task(UploadTaskStatus.FAILED) for _ in range(4)]
        assert _session(tasks).failed_tasks == 4


# ===========================================================================
# UploadSession — cancelled_tasks property
# ===========================================================================

class TestUploadSessionCancelledTasks:
    def test_no_cancelled_returns_zero(self):
        tasks = [_task(UploadTaskStatus.COMPLETED)]
        assert _session(tasks).cancelled_tasks == 0

    def test_one_cancelled_counted(self):
        tasks = [_task(UploadTaskStatus.CANCELLED), _task(UploadTaskStatus.COMPLETED)]
        assert _session(tasks).cancelled_tasks == 1


# ===========================================================================
# UploadSession — progress_percent property
# ===========================================================================

class TestUploadSessionProgressPercent:
    def test_empty_session_progress_is_zero(self):
        assert _session().progress_percent == pytest.approx(0.0)

    def test_all_complete_progress_is_100(self):
        tasks = [_task(progress=100.0) for _ in range(3)]
        assert _session(tasks).progress_percent == pytest.approx(100.0)

    def test_half_complete_progress_is_50(self):
        tasks = [_task(progress=100.0), _task(progress=0.0)]
        assert _session(tasks).progress_percent == pytest.approx(50.0)

    def test_average_of_all_tasks(self):
        tasks = [_task(progress=40.0), _task(progress=80.0)]
        assert _session(tasks).progress_percent == pytest.approx(60.0)

    def test_returns_float(self):
        assert isinstance(_session([_task()]).progress_percent, float)


# ===========================================================================
# UploadSession — is_complete property
# ===========================================================================

class TestUploadSessionIsComplete:
    def test_empty_session_is_complete(self):
        # all() on empty iterable is True
        assert _session().is_complete is True

    def test_all_completed_is_complete(self):
        tasks = [_task(UploadTaskStatus.COMPLETED) for _ in range(2)]
        assert _session(tasks).is_complete is True

    def test_all_failed_is_complete(self):
        tasks = [_task(UploadTaskStatus.FAILED) for _ in range(2)]
        assert _session(tasks).is_complete is True

    def test_all_cancelled_is_complete(self):
        tasks = [_task(UploadTaskStatus.CANCELLED) for _ in range(2)]
        assert _session(tasks).is_complete is True

    def test_mixed_terminal_statuses_is_complete(self):
        tasks = [
            _task(UploadTaskStatus.COMPLETED),
            _task(UploadTaskStatus.FAILED),
            _task(UploadTaskStatus.CANCELLED),
        ]
        assert _session(tasks).is_complete is True

    def test_queued_task_not_complete(self):
        tasks = [_task(UploadTaskStatus.COMPLETED), _task(UploadTaskStatus.QUEUED)]
        assert _session(tasks).is_complete is False

    def test_extracting_task_not_complete(self):
        tasks = [_task(UploadTaskStatus.EXTRACTING)]
        assert _session(tasks).is_complete is False

    def test_returns_bool(self):
        assert isinstance(_session([_task()]).is_complete, bool)


# ===========================================================================
# UploadProgressUpdate dataclass
# ===========================================================================

class TestUploadProgressUpdate:
    def test_required_fields_stored(self):
        u = UploadProgressUpdate(
            session_id="s1",
            task_id="t1",
            file_path="/tmp/file.pdf",
            status=UploadTaskStatus.COMPLETED,
            progress_percent=100.0,
        )
        assert u.session_id == "s1"
        assert u.task_id == "t1"
        assert u.file_path == "/tmp/file.pdf"
        assert u.status == UploadTaskStatus.COMPLETED
        assert u.progress_percent == pytest.approx(100.0)

    def test_default_message_is_empty_string(self):
        u = UploadProgressUpdate("s", "t", "/f", UploadTaskStatus.QUEUED, 0.0)
        assert u.message == ""

    def test_default_error_is_none(self):
        u = UploadProgressUpdate("s", "t", "/f", UploadTaskStatus.QUEUED, 0.0)
        assert u.error is None

    def test_custom_message_stored(self):
        u = UploadProgressUpdate("s", "t", "/f", UploadTaskStatus.EXTRACTING, 10.0,
                                 message="Extracting text...")
        assert u.message == "Extracting text..."

    def test_error_stored(self):
        u = UploadProgressUpdate("s", "t", "/f", UploadTaskStatus.FAILED, 0.0,
                                 error="File not found")
        assert u.error == "File not found"


# ===========================================================================
# RAGUploadQueueManager constants
# ===========================================================================

class TestRAGUploadQueueManagerConstants:
    def test_max_concurrent_uploads(self):
        assert RAGUploadQueueManager.MAX_CONCURRENT_UPLOADS == 3

    def test_session_max_age_hours(self):
        assert RAGUploadQueueManager.SESSION_MAX_AGE_HOURS == 24
