"""
Centralized Thread Pool Manager

This module provides a centralized thread pool for the Medical Assistant application.
Using a shared thread pool instead of creating threads ad-hoc provides several benefits:
- Resource efficiency: Limits the number of concurrent threads
- Better debugging: Named threads with consistent naming
- Graceful shutdown: Proper cleanup on application exit
- Monitoring: Track pending tasks and thread usage

Usage:
    from utils.thread_pool import ThreadPoolManager, submit_task, run_in_background

    # Option 1: Use the module-level functions
    future = submit_task(my_function, arg1, arg2)
    result = future.result()

    # Option 2: Use the class directly
    executor = ThreadPoolManager.get_executor()
    future = executor.submit(my_function, arg1, arg2)

    # Option 3: Use the run_in_background helper
    run_in_background(my_function, on_complete=callback, on_error=error_handler, app=app)

    # Cleanup on application exit
    ThreadPoolManager.shutdown()
"""

import logging
import threading
import atexit
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional, Callable, Any, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ThreadPoolManager:
    """Centralized manager for application thread pools.

    This class provides a singleton thread pool that can be used throughout
    the application for background tasks. It implements the lazy initialization
    pattern with thread-safe double-checked locking.

    Attributes:
        DEFAULT_MAX_WORKERS: Default maximum number of worker threads
        THREAD_NAME_PREFIX: Prefix for worker thread names
    """

    DEFAULT_MAX_WORKERS: int = 4
    THREAD_NAME_PREFIX: str = "medical_assistant"

    _executor: Optional[ThreadPoolExecutor] = None
    _lock = threading.Lock()
    _shutdown_called: bool = False

    @classmethod
    def get_executor(cls, max_workers: Optional[int] = None) -> ThreadPoolExecutor:
        """Get or create the shared thread pool executor.

        Thread-safe implementation using double-checked locking pattern.

        Args:
            max_workers: Maximum number of worker threads (only used on first call)

        Returns:
            ThreadPoolExecutor instance
        """
        if cls._executor is None:
            with cls._lock:
                if cls._executor is None:
                    workers = max_workers or cls.DEFAULT_MAX_WORKERS
                    cls._executor = ThreadPoolExecutor(
                        max_workers=workers,
                        thread_name_prefix=cls.THREAD_NAME_PREFIX
                    )
                    logger.info(f"Created thread pool with {workers} workers")

        return cls._executor

    @classmethod
    def submit(cls, fn: Callable[..., T], *args, **kwargs) -> Future:
        """Submit a task to the thread pool.

        Args:
            fn: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Future representing the pending result
        """
        executor = cls.get_executor()
        future = executor.submit(fn, *args, **kwargs)
        logger.debug(f"Submitted task: {fn.__name__}")
        return future

    @classmethod
    def shutdown(cls, wait: bool = True, cancel_futures: bool = False) -> None:
        """Shutdown the thread pool.

        This should be called when the application is closing to ensure
        all threads are properly terminated.

        Args:
            wait: If True, wait for pending tasks to complete
            cancel_futures: If True, cancel pending tasks (Python 3.9+)
        """
        with cls._lock:
            if cls._executor and not cls._shutdown_called:
                cls._shutdown_called = True
                logger.info("Shutting down thread pool...")

                try:
                    # Python 3.9+ supports cancel_futures
                    cls._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
                except TypeError:
                    # Python 3.8 compatibility
                    cls._executor.shutdown(wait=wait)

                cls._executor = None
                logger.info("Thread pool shutdown complete")

    @classmethod
    def is_running(cls) -> bool:
        """Check if the thread pool is running.

        Returns:
            True if the thread pool is active, False otherwise
        """
        return cls._executor is not None and not cls._shutdown_called

    @classmethod
    def get_stats(cls) -> dict:
        """Get statistics about the thread pool.

        Returns:
            Dictionary with thread pool statistics
        """
        if cls._executor is None:
            return {"status": "not_initialized"}

        return {
            "status": "running" if not cls._shutdown_called else "shutdown",
            "max_workers": cls.DEFAULT_MAX_WORKERS,
        }

    @classmethod
    def reset(cls) -> None:
        """Reset the thread pool manager.

        This shuts down any existing executor and resets the state,
        allowing a new executor to be created. Useful for testing.
        """
        cls.shutdown(wait=True)
        with cls._lock:
            cls._shutdown_called = False
            cls._executor = None


# Module-level convenience functions

def submit_task(fn: Callable[..., T], *args, **kwargs) -> Future:
    """Submit a task to the centralized thread pool.

    This is a convenience function that wraps ThreadPoolManager.submit().

    Args:
        fn: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Future representing the pending result

    Example:
        future = submit_task(process_file, filepath, options)
        result = future.result(timeout=30)
    """
    return ThreadPoolManager.submit(fn, *args, **kwargs)


def run_in_background(
    fn: Callable[..., T],
    *args,
    on_complete: Optional[Callable[[T], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    app=None,
    **kwargs
) -> Future:
    """Run a function in the background with optional callbacks.

    This function provides a convenient way to run background tasks with
    result and error handling. If an app is provided, callbacks are
    scheduled on the main thread using app.after().

    Args:
        fn: Function to execute in background
        *args: Positional arguments for the function
        on_complete: Optional callback for successful completion
        on_error: Optional callback for error handling
        app: Optional tkinter app for scheduling callbacks on main thread
        **kwargs: Keyword arguments for the function

    Returns:
        Future representing the pending result

    Example:
        def process_data():
            return expensive_computation()

        def on_done(result):
            label.config(text=f"Result: {result}")

        def on_fail(error):
            label.config(text=f"Error: {error}")

        run_in_background(
            process_data,
            on_complete=on_done,
            on_error=on_fail,
            app=app
        )
    """
    def task_wrapper():
        try:
            result = fn(*args, **kwargs)
            if on_complete:
                if app:
                    app.after(0, lambda: on_complete(result))
                else:
                    on_complete(result)
            return result
        except Exception as e:
            logger.error(f"Error in background task {fn.__name__}: {e}", exc_info=True)
            if on_error:
                if app:
                    app.after(0, lambda: on_error(e))
                else:
                    on_error(e)
            raise

    return ThreadPoolManager.submit(task_wrapper)


def background_task(
    on_complete: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    app_getter: Optional[Callable] = None
):
    """Decorator to run a function in the background thread pool.

    Args:
        on_complete: Optional callback for successful completion
        on_error: Optional callback for error handling
        app_getter: Optional callable that returns the tkinter app

    Returns:
        Decorator function

    Example:
        @background_task(on_complete=lambda r: print(f"Done: {r}"))
        def process_file(filepath):
            return do_processing(filepath)

        # Call starts background task, returns Future
        future = process_file("/path/to/file.txt")
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., Future]:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> Future:
            app = app_getter() if app_getter else None
            return run_in_background(
                fn, *args,
                on_complete=on_complete,
                on_error=on_error,
                app=app,
                **kwargs
            )
        return wrapper
    return decorator


class TaskQueue:
    """A simple task queue for managing sequential background tasks.

    This class provides a way to queue tasks that should be executed
    sequentially rather than concurrently. Useful for operations that
    must be serialized (e.g., database writes).

    Example:
        queue = TaskQueue()
        queue.enqueue(task1)
        queue.enqueue(task2)  # Runs after task1 completes
        queue.enqueue(task3)  # Runs after task2 completes
    """

    def __init__(self):
        self._queue: list = []
        self._lock = threading.Lock()
        self._running = False
        self._current_future: Optional[Future] = None

    def enqueue(self, fn: Callable, *args, **kwargs) -> Future:
        """Add a task to the queue.

        Args:
            fn: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future for this specific task
        """
        future = Future()

        def task():
            try:
                result = fn(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._task_complete()

        with self._lock:
            self._queue.append(task)
            if not self._running:
                self._start_next()

        return future

    def _start_next(self) -> None:
        """Start the next task in the queue."""
        with self._lock:
            if self._queue:
                self._running = True
                task = self._queue.pop(0)
                self._current_future = ThreadPoolManager.submit(task)
            else:
                self._running = False

    def _task_complete(self) -> None:
        """Called when a task completes."""
        self._start_next()

    @property
    def pending_count(self) -> int:
        """Number of pending tasks in the queue."""
        with self._lock:
            return len(self._queue) + (1 if self._running else 0)

    @property
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self.pending_count == 0


# Register shutdown handler
def _cleanup():
    """Cleanup function called at application exit."""
    if ThreadPoolManager.is_running():
        ThreadPoolManager.shutdown(wait=False)


atexit.register(_cleanup)
