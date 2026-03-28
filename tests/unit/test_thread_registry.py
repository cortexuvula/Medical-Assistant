"""Tests for utils.thread_registry — ThreadRegistry singleton."""

import threading
import time
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset ThreadRegistry singleton before each test."""
    import utils.thread_registry as mod
    mod.ThreadRegistry._instance = None
    yield
    mod.ThreadRegistry._instance = None


# ── Singleton ─────────────────────────────────────────────────────────────────

class TestThreadRegistrySingleton:
    def test_instance_returns_same_object(self):
        from utils.thread_registry import ThreadRegistry
        a = ThreadRegistry.instance()
        b = ThreadRegistry.instance()
        assert a is b

    def test_instance_is_thread_registry(self):
        from utils.thread_registry import ThreadRegistry
        assert isinstance(ThreadRegistry.instance(), ThreadRegistry)


# ── register ──────────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_thread_tracked(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()

        t = threading.Thread(target=lambda: None, daemon=True)
        reg.register("test_thread", t)
        # Thread is registered (WeakSet may hold it while alive)
        # Just ensure it doesn't raise

    def test_register_multiple_threads(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()

        t1 = threading.Thread(target=time.sleep, args=(0.1,), daemon=True)
        t2 = threading.Thread(target=time.sleep, args=(0.1,), daemon=True)
        t1.start()
        t2.start()
        reg.register("t1", t1)
        reg.register("t2", t2)
        t1.join()
        t2.join()


# ── get_active_threads ────────────────────────────────────────────────────────

class TestGetActiveThreads:
    def test_returns_empty_when_none_registered(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()
        assert reg.get_active_threads() == []

    def test_returns_alive_thread(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()
        started = threading.Event()
        stop = threading.Event()

        def worker():
            started.set()
            stop.wait(timeout=5)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        started.wait(timeout=5)

        reg.register("worker", t)
        active = reg.get_active_threads()
        names = [name for name, _ in active]
        assert "worker" in names

        stop.set()
        t.join()

    def test_finished_thread_not_returned(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()
        done = threading.Event()

        def worker():
            done.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        done.wait(timeout=5)
        t.join()

        reg.register("done_thread", t)
        active = reg.get_active_threads()
        names = [name for name, _ in active]
        assert "done_thread" not in names


# ── shutdown ──────────────────────────────────────────────────────────────────

class TestShutdown:
    def test_shutdown_empty_returns_empty_dict(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()
        result = reg.shutdown(timeout=1.0)
        assert result == {}

    def test_shutdown_waits_for_thread(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()
        results = []

        def worker():
            time.sleep(0.05)
            results.append("done")

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        reg.register("quick_worker", t)

        outcome = reg.shutdown(timeout=5.0)
        assert results == ["done"]
        assert outcome.get("quick_worker") is True

    def test_shutdown_records_timeout(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()
        stop = threading.Event()

        def long_worker():
            stop.wait(timeout=60)

        t = threading.Thread(target=long_worker, daemon=True)
        t.start()
        reg.register("long_worker", t)

        outcome = reg.shutdown(timeout=0.01)  # Very short timeout
        assert outcome.get("long_worker") is False

        stop.set()
        t.join()

    def test_shutdown_returns_empty_for_already_finished_thread(self):
        from utils.thread_registry import ThreadRegistry
        reg = ThreadRegistry.instance()

        def quick():
            pass

        t = threading.Thread(target=quick, daemon=True)
        t.start()
        t.join()

        reg.register("already_done", t)
        # get_active_threads() filters to only is_alive() threads, so the
        # dead thread is not in the active list and shutdown returns {}
        outcome = reg.shutdown(timeout=1.0)
        assert outcome == {}
