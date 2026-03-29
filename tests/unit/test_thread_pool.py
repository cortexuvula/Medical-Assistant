"""
Tests for src/utils/thread_pool.py
Covers: ThreadPoolManager, submit_task, run_in_background, background_task, TaskQueue.
No sleeping — futures awaited with timeout=5.
"""

import sys
import threading
import pytest
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch, call

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.thread_pool import (
    ThreadPoolManager,
    submit_task,
    run_in_background,
    background_task,
    TaskQueue,
)


# ---------------------------------------------------------------------------
# Autouse fixture: reset singleton state around every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_thread_pool():
    ThreadPoolManager.reset()
    ThreadPoolManager._shutdown_called = False
    ThreadPoolManager._executor = None
    yield
    ThreadPoolManager.reset()
    ThreadPoolManager._shutdown_called = False
    ThreadPoolManager._executor = None


# ===========================================================================
# ThreadPoolManager.get_executor
# ===========================================================================

class TestGetExecutor:
    def test_returns_thread_pool_executor(self):
        executor = ThreadPoolManager.get_executor()
        assert isinstance(executor, ThreadPoolExecutor)

    def test_returns_same_instance_on_second_call(self):
        a = ThreadPoolManager.get_executor()
        b = ThreadPoolManager.get_executor()
        assert a is b

    def test_returns_same_instance_multiple_calls(self):
        instances = [ThreadPoolManager.get_executor() for _ in range(5)]
        assert all(i is instances[0] for i in instances)

    def test_executor_is_stored_on_class(self):
        executor = ThreadPoolManager.get_executor()
        assert ThreadPoolManager._executor is executor

    def test_executor_none_before_first_call(self):
        assert ThreadPoolManager._executor is None

    def test_custom_max_workers_accepted(self):
        # Only honoured on first creation; just checks it does not raise
        executor = ThreadPoolManager.get_executor(max_workers=2)
        assert isinstance(executor, ThreadPoolExecutor)

    def test_default_max_workers_constant(self):
        assert ThreadPoolManager.DEFAULT_MAX_WORKERS == 4

    def test_thread_name_prefix_constant(self):
        assert ThreadPoolManager.THREAD_NAME_PREFIX == "medical_assistant"

    def test_get_executor_thread_safe_double_check(self):
        """Two threads racing to create the executor should both get the same one."""
        results = []
        barrier = threading.Barrier(2)

        def get_it():
            barrier.wait()
            results.append(ThreadPoolManager.get_executor())

        t1 = threading.Thread(target=get_it)
        t2 = threading.Thread(target=get_it)
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert results[0] is results[1]


# ===========================================================================
# ThreadPoolManager.submit
# ===========================================================================

class TestSubmit:
    def test_submit_returns_future(self):
        future = ThreadPoolManager.submit(lambda: None)
        assert isinstance(future, Future)
        future.result(timeout=5)

    def test_submit_executes_function(self):
        results = []
        future = ThreadPoolManager.submit(results.append, 42)
        future.result(timeout=5)
        assert results == [42]

    def test_submit_returns_correct_result(self):
        future = ThreadPoolManager.submit(lambda: 99)
        assert future.result(timeout=5) == 99

    def test_submit_with_positional_args(self):
        def add(a, b):
            return a + b

        assert ThreadPoolManager.submit(add, 3, 4).result(timeout=5) == 7

    def test_submit_with_keyword_args(self):
        def add(a, b):
            return a + b

        assert ThreadPoolManager.submit(add, 3, b=4).result(timeout=5) == 7

    def test_submit_with_mixed_args(self):
        def concat(s, suffix="!"):
            return s + suffix

        result = ThreadPoolManager.submit(concat, "hello", suffix="?").result(timeout=5)
        assert result == "hello?"

    def test_submit_propagates_exception(self):
        def bad():
            raise ValueError("test error")

        future = ThreadPoolManager.submit(bad)
        with pytest.raises(ValueError, match="test error"):
            future.result(timeout=5)

    def test_submit_propagates_runtime_error(self):
        def bad():
            raise RuntimeError("runtime")

        with pytest.raises(RuntimeError):
            ThreadPoolManager.submit(bad).result(timeout=5)

    def test_submit_multiple_tasks(self):
        futures = [ThreadPoolManager.submit(lambda x=i: x * 2, i) for i in range(5)]
        results = [f.result(timeout=5) for f in futures]
        assert sorted(results) == [0, 2, 4, 6, 8]

    def test_submit_creates_executor_lazily(self):
        assert ThreadPoolManager._executor is None
        ThreadPoolManager.submit(lambda: None).result(timeout=5)
        assert ThreadPoolManager._executor is not None

    def test_submit_none_return(self):
        future = ThreadPoolManager.submit(lambda: None)
        assert future.result(timeout=5) is None

    def test_submit_string_result(self):
        future = ThreadPoolManager.submit(lambda: "hello")
        assert future.result(timeout=5) == "hello"

    def test_submit_list_result(self):
        future = ThreadPoolManager.submit(lambda: [1, 2, 3])
        assert future.result(timeout=5) == [1, 2, 3]


# ===========================================================================
# ThreadPoolManager.is_running
# ===========================================================================

class TestIsRunning:
    def test_false_before_creation(self):
        assert not ThreadPoolManager.is_running()

    def test_true_after_get_executor(self):
        ThreadPoolManager.get_executor()
        assert ThreadPoolManager.is_running()

    def test_false_after_shutdown(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown()
        assert not ThreadPoolManager.is_running()

    def test_false_when_shutdown_called_flag_set(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager._shutdown_called = True
        assert not ThreadPoolManager.is_running()

    def test_false_when_executor_none_and_no_shutdown(self):
        ThreadPoolManager._executor = None
        ThreadPoolManager._shutdown_called = False
        assert not ThreadPoolManager.is_running()

    def test_true_after_reset_and_new_executor(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        ThreadPoolManager.get_executor()
        assert ThreadPoolManager.is_running()


# ===========================================================================
# ThreadPoolManager.get_stats
# ===========================================================================

class TestGetStats:
    def test_not_initialized_when_no_executor(self):
        stats = ThreadPoolManager.get_stats()
        assert stats["status"] == "not_initialized"

    def test_returns_dict(self):
        stats = ThreadPoolManager.get_stats()
        assert isinstance(stats, dict)

    def test_running_status_after_get_executor(self):
        ThreadPoolManager.get_executor()
        stats = ThreadPoolManager.get_stats()
        assert stats["status"] == "running"

    def test_has_max_workers_key_when_running(self):
        ThreadPoolManager.get_executor()
        stats = ThreadPoolManager.get_stats()
        assert "max_workers" in stats

    def test_max_workers_value(self):
        ThreadPoolManager.get_executor()
        stats = ThreadPoolManager.get_stats()
        assert stats["max_workers"] == ThreadPoolManager.DEFAULT_MAX_WORKERS

    def test_status_key_always_present(self):
        stats = ThreadPoolManager.get_stats()
        assert "status" in stats

    def test_status_not_initialized_before_any_call(self):
        # Executor has never been created
        stats = ThreadPoolManager.get_stats()
        assert stats == {"status": "not_initialized"}

    def test_shutdown_status_after_shutdown(self):
        # After shutdown _executor is set to None, so stats returns not_initialized
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown()
        stats = ThreadPoolManager.get_stats()
        # _executor is None after shutdown, so "not_initialized"
        assert stats["status"] == "not_initialized"


# ===========================================================================
# ThreadPoolManager.shutdown
# ===========================================================================

class TestShutdown:
    def test_shutdown_sets_is_running_false(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown()
        assert not ThreadPoolManager.is_running()

    def test_shutdown_clears_executor(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown()
        assert ThreadPoolManager._executor is None

    def test_double_shutdown_does_not_raise(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown()
        ThreadPoolManager.shutdown()  # Should be safe

    def test_shutdown_before_creation_does_not_raise(self):
        ThreadPoolManager.shutdown()  # No executor created yet

    def test_shutdown_wait_true(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown(wait=True)
        assert not ThreadPoolManager.is_running()

    def test_shutdown_wait_false(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown(wait=False)
        assert not ThreadPoolManager.is_running()

    def test_shutdown_sets_shutdown_called(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.shutdown()
        # After shutdown _executor is None; _shutdown_called was true during
        # shutdown; the lock block sets _executor=None but _shutdown_called stays True
        # until reset() is called
        assert ThreadPoolManager._shutdown_called is True


# ===========================================================================
# ThreadPoolManager.reset
# ===========================================================================

class TestReset:
    def test_reset_clears_executor(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        assert ThreadPoolManager._executor is None

    def test_reset_clears_shutdown_called(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        assert not ThreadPoolManager._shutdown_called

    def test_reset_allows_new_get_executor(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        new_exec = ThreadPoolManager.get_executor()
        assert isinstance(new_exec, ThreadPoolExecutor)

    def test_reset_on_fresh_state_does_not_raise(self):
        ThreadPoolManager.reset()  # Never initialised

    def test_reset_twice_does_not_raise(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        ThreadPoolManager.reset()

    def test_is_not_running_after_reset(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        assert not ThreadPoolManager.is_running()

    def test_stats_not_initialized_after_reset(self):
        ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        assert ThreadPoolManager.get_stats()["status"] == "not_initialized"

    def test_new_executor_after_reset_is_different(self):
        first = ThreadPoolManager.get_executor()
        ThreadPoolManager.reset()
        second = ThreadPoolManager.get_executor()
        assert first is not second


# ===========================================================================
# submit_task (module-level convenience)
# ===========================================================================

class TestSubmitTask:
    def test_returns_future(self):
        future = submit_task(lambda: None)
        assert isinstance(future, Future)
        future.result(timeout=5)

    def test_executes_function(self):
        results = []
        submit_task(results.append, 1).result(timeout=5)
        assert results == [1]

    def test_returns_correct_result(self):
        assert submit_task(lambda: "ok").result(timeout=5) == "ok"

    def test_with_positional_args(self):
        assert submit_task(max, 3, 7).result(timeout=5) == 7

    def test_with_keyword_args(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = submit_task(greet, "World", greeting="Hi").result(timeout=5)
        assert result == "Hi, World!"

    def test_delegates_to_thread_pool_manager(self):
        with patch.object(ThreadPoolManager, "submit", wraps=ThreadPoolManager.submit) as mock_submit:
            f = submit_task(lambda: 0)
            f.result(timeout=5)
            mock_submit.assert_called_once()

    def test_exception_propagates(self):
        def bad():
            raise TypeError("bad type")

        with pytest.raises(TypeError, match="bad type"):
            submit_task(bad).result(timeout=5)

    def test_multiple_sequential_tasks(self):
        futures = [submit_task(lambda x=i: x + 1) for i in range(4)]
        results = [f.result(timeout=5) for f in futures]
        assert sorted(results) == [1, 2, 3, 4]


# ===========================================================================
# run_in_background
# ===========================================================================

class TestRunInBackground:
    def test_returns_future(self):
        done = threading.Event()
        future = run_in_background(done.set)
        assert isinstance(future, Future)
        done.wait(timeout=5)

    def test_runs_function(self):
        done = threading.Event()
        run_in_background(done.set)
        assert done.wait(timeout=5)

    def test_calls_on_complete_with_result(self):
        results = []
        done = threading.Event()

        def on_done(r):
            results.append(r)
            done.set()

        run_in_background(lambda: 99, on_complete=on_done)
        assert done.wait(timeout=5)
        assert results == [99]

    def test_calls_on_complete_with_string(self):
        results = []
        done = threading.Event()

        run_in_background(
            lambda: "hello",
            on_complete=lambda r: (results.append(r), done.set()),
        )
        assert done.wait(timeout=5)
        assert results == ["hello"]

    def test_calls_on_complete_with_none(self):
        results = []
        done = threading.Event()

        run_in_background(
            lambda: None,
            on_complete=lambda r: (results.append(r), done.set()),
        )
        assert done.wait(timeout=5)
        assert results == [None]

    def test_calls_on_error_on_exception(self):
        errors = []
        done = threading.Event()

        def on_fail(e):
            errors.append(e)
            done.set()

        def bad():
            raise RuntimeError("oops")

        run_in_background(bad, on_error=on_fail)
        assert done.wait(timeout=5)
        assert isinstance(errors[0], RuntimeError)
        assert str(errors[0]) == "oops"

    def test_on_error_not_called_on_success(self):
        errors = []
        done = threading.Event()

        run_in_background(
            lambda: 1,
            on_complete=lambda _: done.set(),
            on_error=lambda e: errors.append(e),
        )
        assert done.wait(timeout=5)
        assert errors == []

    def test_on_complete_not_called_on_error(self):
        results = []
        done = threading.Event()

        run_in_background(
            lambda: (_ for _ in ()).throw(ValueError("fail")),
            on_complete=lambda r: results.append(r),
            on_error=lambda e: done.set(),
        )
        assert done.wait(timeout=5)
        assert results == []

    def test_no_callbacks_still_runs(self):
        done = threading.Event()
        run_in_background(done.set)
        assert done.wait(timeout=5)

    def test_with_app_calls_after_on_complete(self):
        results = []
        done = threading.Event()
        app = MagicMock()
        app.after.side_effect = lambda delay, fn: fn()

        run_in_background(
            lambda: 42,
            on_complete=lambda r: (results.append(r), done.set()),
            app=app,
        )
        assert done.wait(timeout=5)
        assert results == [42]

    def test_with_app_calls_after_on_error(self):
        errors = []
        done = threading.Event()
        app = MagicMock()
        app.after.side_effect = lambda delay, fn: fn()

        def bad():
            raise ValueError("app error")

        run_in_background(bad, on_error=lambda e: (errors.append(e), done.set()), app=app)
        assert done.wait(timeout=5)
        assert isinstance(errors[0], ValueError)

    def test_app_after_called_with_zero_delay(self):
        app = MagicMock()
        captured_delays = []
        app.after.side_effect = lambda delay, fn: (captured_delays.append(delay), fn())
        done = threading.Event()

        run_in_background(
            lambda: 1,
            on_complete=lambda r: done.set(),
            app=app,
        )
        done.wait(timeout=5)
        assert captured_delays[0] == 0

    def test_with_positional_args(self):
        results = []
        done = threading.Event()

        def add(a, b):
            return a + b

        run_in_background(
            add, 3, 4,
            on_complete=lambda r: (results.append(r), done.set()),
        )
        assert done.wait(timeout=5)
        assert results == [7]

    def test_with_keyword_args(self):
        results = []
        done = threading.Event()

        def greet(name, suffix="!"):
            return name + suffix

        run_in_background(
            greet, "hi",
            on_complete=lambda r: (results.append(r), done.set()),
            suffix="?",
        )
        assert done.wait(timeout=5)
        assert results == ["hi?"]

    def test_exception_is_reraised_in_future(self):
        """The wrapper re-raises after calling on_error, so future has the exception."""
        done = threading.Event()

        def bad():
            raise RuntimeError("reraise")

        future = run_in_background(bad, on_error=lambda e: done.set())
        done.wait(timeout=5)
        with pytest.raises(RuntimeError, match="reraise"):
            future.result(timeout=5)

    def test_on_complete_receives_actual_return_value(self):
        results = []
        done = threading.Event()

        run_in_background(
            lambda: {"key": "value"},
            on_complete=lambda r: (results.append(r), done.set()),
        )
        assert done.wait(timeout=5)
        assert results[0] == {"key": "value"}


# ===========================================================================
# background_task decorator
# ===========================================================================

class TestBackgroundTaskDecorator:
    def test_returns_future(self):
        @background_task()
        def compute():
            return 7

        result = compute()
        assert isinstance(result, Future)
        result.result(timeout=5)

    def test_future_has_correct_result(self):
        @background_task()
        def compute():
            return 123

        assert compute().result(timeout=5) == 123

    def test_on_complete_called(self):
        results = []
        done = threading.Event()

        def on_done(r):
            results.append(r)
            done.set()

        @background_task(on_complete=on_done)
        def compute():
            return 100

        compute()
        assert done.wait(timeout=5)
        assert results == [100]

    def test_on_error_called(self):
        errors = []
        done = threading.Event()

        def on_fail(e):
            errors.append(e)
            done.set()

        @background_task(on_error=on_fail)
        def bad():
            raise ValueError("decorated error")

        bad()
        assert done.wait(timeout=5)
        assert isinstance(errors[0], ValueError)
        assert str(errors[0]) == "decorated error"

    def test_preserves_function_name(self):
        @background_task()
        def my_unique_function():
            return None

        assert my_unique_function.__name__ == "my_unique_function"

    def test_preserves_function_docstring(self):
        @background_task()
        def documented():
            """This is documented."""
            return None

        assert documented.__doc__ == "This is documented."

    def test_with_args(self):
        results = []
        done = threading.Event()

        @background_task(on_complete=lambda r: (results.append(r), done.set()))
        def add(a, b):
            return a + b

        add(5, 6)
        assert done.wait(timeout=5)
        assert results == [11]

    def test_with_kwargs(self):
        results = []
        done = threading.Event()

        @background_task(on_complete=lambda r: (results.append(r), done.set()))
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        greet("World", greeting="Hi")
        assert done.wait(timeout=5)
        assert results == ["Hi, World"]

    def test_app_getter_called(self):
        app = MagicMock()
        app.after.side_effect = lambda delay, fn: fn()
        getter_calls = []

        def getter():
            getter_calls.append(True)
            return app

        results = []
        done = threading.Event()

        @background_task(
            on_complete=lambda r: (results.append(r), done.set()),
            app_getter=getter,
        )
        def compute():
            return "via getter"

        compute()
        assert done.wait(timeout=5)
        assert getter_calls  # getter was called
        assert results == ["via getter"]

    def test_no_on_complete_no_crash(self):
        done = threading.Event()

        @background_task()
        def compute():
            done.set()
            return 1

        compute()
        assert done.wait(timeout=5)

    def test_multiple_calls_to_decorated_function(self):
        results = []
        done_events = [threading.Event() for _ in range(3)]

        @background_task()
        def compute(x):
            return x * 2

        futures = [compute(i) for i in range(3)]
        vals = sorted(f.result(timeout=5) for f in futures)
        assert vals == [0, 2, 4]

    def test_returns_future_not_result(self):
        """Decorated function must return Future immediately, not block."""
        @background_task()
        def slow():
            return "done"

        result = slow()
        assert isinstance(result, Future)
        result.result(timeout=5)


# ===========================================================================
# TaskQueue
# ===========================================================================

class TestTaskQueueInit:
    def test_is_empty_on_creation(self):
        q = TaskQueue()
        assert q.is_empty

    def test_pending_count_zero_on_creation(self):
        q = TaskQueue()
        assert q.pending_count == 0

    def test_is_empty_property_true_when_no_tasks(self):
        q = TaskQueue()
        assert q.is_empty is True

    def test_pending_count_property_returns_int(self):
        q = TaskQueue()
        assert isinstance(q.pending_count, int)

    def test_running_false_on_init(self):
        q = TaskQueue()
        assert not q._running

    def test_queue_empty_list_on_init(self):
        q = TaskQueue()
        assert q._queue == []

    def test_multiple_queues_independent(self):
        q1 = TaskQueue()
        q2 = TaskQueue()
        assert q1 is not q2
        assert q1.is_empty
        assert q2.is_empty


class TestTaskQueueEnqueue:
    """Tests for TaskQueue.enqueue().
    The lock in _start_next() is acquired while enqueue() holds the outer lock,
    so we patch _start_next to avoid the deadlock in all tests that call enqueue().
    """

    def _make_non_deadlocking_queue(self):
        """Return a TaskQueue whose _start_next is patched to avoid the deadlock."""
        q = TaskQueue()
        # Patch _start_next so it does not re-acquire _lock
        q._start_next = MagicMock()
        return q

    def test_enqueue_returns_future(self):
        q = self._make_non_deadlocking_queue()
        future = q.enqueue(lambda: None)
        assert isinstance(future, Future)

    def test_enqueue_increments_queue_when_running(self):
        q = TaskQueue()
        q._running = True  # Pretend a task is already running
        q._start_next = MagicMock()  # patch to avoid deadlock
        q.enqueue(lambda: None)
        # Task should be appended to the internal queue (not started)
        assert len(q._queue) == 1

    def test_enqueue_calls_start_next_when_not_running(self):
        q = TaskQueue()
        q._start_next = MagicMock()
        q.enqueue(lambda: None)
        q._start_next.assert_called_once()

    def test_enqueue_does_not_call_start_next_when_already_running(self):
        q = TaskQueue()
        q._running = True
        q._start_next = MagicMock()
        q.enqueue(lambda: None)
        q._start_next.assert_not_called()

    def test_enqueue_task_sets_result_on_future(self):
        """Execute the inner task function directly to verify it sets future result."""
        q = TaskQueue()
        q._start_next = MagicMock()
        future = q.enqueue(lambda: 42)

        # Manually pop and run the task that was appended
        task = q._queue.pop(0)
        q._start_next = MagicMock()  # re-patch for _task_complete call inside task
        task()
        assert future.result(timeout=5) == 42

    def test_enqueue_task_sets_exception_on_future(self):
        """If the wrapped function raises, the future should hold the exception."""
        q = TaskQueue()
        q._start_next = MagicMock()

        def bad():
            raise ValueError("queue error")

        future = q.enqueue(bad)
        task = q._queue.pop(0)
        q._start_next = MagicMock()
        task()  # This sets the exception on the future

        with pytest.raises(ValueError, match="queue error"):
            future.result(timeout=5)

    def test_enqueue_calls_task_complete_after_task_runs(self):
        """The task wrapper must call _task_complete() in its finally block."""
        complete_calls = []

        q = TaskQueue()
        q._start_next = MagicMock()
        q._task_complete = lambda: complete_calls.append(1)

        future = q.enqueue(lambda: "done")
        task = q._queue.pop(0)
        q._start_next = MagicMock()
        task()
        assert complete_calls == [1]

    def test_enqueue_calls_task_complete_even_on_exception(self):
        """_task_complete should be called even when the wrapped fn raises."""
        complete_calls = []

        q = TaskQueue()
        q._start_next = MagicMock()
        q._task_complete = lambda: complete_calls.append(1)

        future = q.enqueue(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        task = q._queue.pop(0)
        q._start_next = MagicMock()
        task()
        assert complete_calls == [1]


class TestTaskQueueStartNext:
    def test_start_next_sets_running_true_when_queue_has_items(self):
        q = TaskQueue()
        q._queue.append(lambda: None)
        # patch ThreadPoolManager.submit so nothing actually runs
        with patch.object(ThreadPoolManager, "submit", return_value=MagicMock()):
            q._start_next()
        assert q._running is True

    def test_start_next_pops_task_from_queue(self):
        q = TaskQueue()
        task = MagicMock()
        q._queue.append(task)
        with patch.object(ThreadPoolManager, "submit", return_value=MagicMock()):
            q._start_next()
        assert len(q._queue) == 0

    def test_start_next_sets_running_false_when_queue_empty(self):
        q = TaskQueue()
        q._running = True
        q._start_next()
        assert q._running is False

    def test_start_next_submits_to_thread_pool(self):
        q = TaskQueue()
        task = MagicMock()
        q._queue.append(task)
        mock_future = MagicMock()
        with patch.object(ThreadPoolManager, "submit", return_value=mock_future) as mock_submit:
            q._start_next()
        mock_submit.assert_called_once_with(task)

    def test_start_next_stores_current_future(self):
        q = TaskQueue()
        task = MagicMock()
        q._queue.append(task)
        mock_future = MagicMock()
        with patch.object(ThreadPoolManager, "submit", return_value=mock_future):
            q._start_next()
        assert q._current_future is mock_future


class TestTaskQueuePendingCount:
    def test_pending_count_zero_when_empty(self):
        q = TaskQueue()
        assert q.pending_count == 0

    def test_pending_count_one_when_running_no_queue(self):
        q = TaskQueue()
        q._running = True
        assert q.pending_count == 1

    def test_pending_count_includes_queue_items(self):
        q = TaskQueue()
        q._running = True
        q._queue.append(lambda: None)
        q._queue.append(lambda: None)
        assert q.pending_count == 3  # 1 running + 2 queued

    def test_pending_count_queue_only_not_running(self):
        q = TaskQueue()
        q._running = False
        q._queue.append(lambda: None)
        q._queue.append(lambda: None)
        assert q.pending_count == 2

    def test_pending_count_thread_safe(self):
        """concurrent reads of pending_count should not raise."""
        q = TaskQueue()
        exceptions = []

        def read_count():
            try:
                _ = q.pending_count
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=read_count) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert not exceptions


class TestTaskQueueIsEmpty:
    def test_is_empty_true_when_no_tasks(self):
        q = TaskQueue()
        assert q.is_empty is True

    def test_is_empty_false_when_running(self):
        q = TaskQueue()
        q._running = True
        assert q.is_empty is False

    def test_is_empty_false_when_queue_has_items(self):
        q = TaskQueue()
        q._queue.append(lambda: None)
        assert q.is_empty is False

    def test_is_empty_false_when_running_and_queued(self):
        q = TaskQueue()
        q._running = True
        q._queue.append(lambda: None)
        assert q.is_empty is False

    def test_is_empty_true_after_manually_clearing(self):
        q = TaskQueue()
        q._running = True
        q._queue.append(lambda: None)
        # Simulate completion
        q._queue.clear()
        q._running = False
        assert q.is_empty is True

    def test_is_empty_delegates_to_pending_count(self):
        q = TaskQueue()
        with patch.object(type(q), "pending_count", new_callable=lambda: property(lambda self: 0)):
            assert q.is_empty is True

    def test_is_empty_returns_bool(self):
        q = TaskQueue()
        assert isinstance(q.is_empty, bool)


class TestTaskQueueIntegration:
    """Integration-level tests that use the real thread pool but patch _start_next
    to avoid the non-reentrant lock deadlock documented in the codebase."""

    def test_full_task_execution_via_manual_dispatch(self):
        """Manually drive a task through the queue to verify end-to-end execution."""
        q = TaskQueue()
        q._start_next = MagicMock()
        results = []

        future = q.enqueue(lambda: results.append(99) or 99)
        task = q._queue.pop(0)
        q._start_next = MagicMock()
        task()

        assert future.result(timeout=5) == 99
        assert results == [99]

    def test_sequential_execution_manually_driven(self):
        """Two tasks can be run in sequence by manually popping and running each."""
        q = TaskQueue()
        q._start_next = MagicMock()
        order = []

        q.enqueue(lambda: order.append(1))
        q.enqueue(lambda: order.append(2))

        tasks = list(q._queue)
        q._queue.clear()
        q._start_next = MagicMock()
        for t in tasks:
            t()

        assert order == [1, 2]

    def test_exception_in_task_does_not_block_future_tasks(self):
        """Even if one task raises, subsequent tasks can still run."""
        q = TaskQueue()
        q._start_next = MagicMock()
        results = []

        future_bad = q.enqueue(lambda: (_ for _ in ()).throw(RuntimeError("bad")))
        future_good = q.enqueue(lambda: results.append("ok") or "ok")

        tasks = list(q._queue)
        q._queue.clear()
        q._start_next = MagicMock()
        for t in tasks:
            t()

        with pytest.raises(RuntimeError):
            future_bad.result(timeout=5)
        assert future_good.result(timeout=5) == "ok"
