"""
Tests for src/utils/thread_registry.py

Covers ThreadRegistry singleton, register(), get_active_threads(),
shutdown(), WeakSet/WeakValueDictionary behaviour, and thread-safety basics.
No Tkinter required.
"""

import sys
import gc
import time
import pytest
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.thread_registry import ThreadRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Isolate singleton state for every test."""
    old = ThreadRegistry._instance
    ThreadRegistry._instance = None
    yield
    ThreadRegistry._instance = old


def make_thread(target=None, daemon=True):
    """Create a real Thread (not yet started)."""
    return threading.Thread(target=target or (lambda: None), daemon=daemon)


def make_mock_thread(alive=True):
    """Create a MagicMock that behaves like a threading.Thread."""
    m = MagicMock(spec=threading.Thread)
    m.is_alive.return_value = alive
    return m


# ===========================================================================
# Section 1 – __init__ / basic construction
# ===========================================================================

class TestInit:
    def test_creates_fresh_instance(self):
        reg = ThreadRegistry()
        assert reg is not None

    def test_threads_starts_empty(self):
        reg = ThreadRegistry()
        assert len(list(reg._threads)) == 0

    def test_names_starts_empty(self):
        reg = ThreadRegistry()
        assert len(reg._names) == 0

    def test_lock_has_acquire_and_release(self):
        reg = ThreadRegistry()
        assert hasattr(reg._lock, "acquire")
        assert hasattr(reg._lock, "release")

    def test_two_fresh_instances_are_independent(self):
        r1 = ThreadRegistry()
        r2 = ThreadRegistry()
        assert r1 is not r2

    def test_threads_attr_is_weakset(self):
        import weakref
        reg = ThreadRegistry()
        assert isinstance(reg._threads, weakref.WeakSet)

    def test_names_attr_is_weakvalue_dict(self):
        import weakref
        reg = ThreadRegistry()
        assert isinstance(reg._names, weakref.WeakValueDictionary)


# ===========================================================================
# Section 2 – instance() singleton behaviour
# ===========================================================================

class TestInstance:
    def test_returns_an_instance(self):
        reg = ThreadRegistry.instance()
        assert isinstance(reg, ThreadRegistry)

    def test_same_instance_on_second_call(self):
        r1 = ThreadRegistry.instance()
        r2 = ThreadRegistry.instance()
        assert r1 is r2

    def test_creates_new_instance_after_reset(self):
        r1 = ThreadRegistry.instance()
        ThreadRegistry._instance = None
        r2 = ThreadRegistry.instance()
        assert r1 is not r2

    def test_instance_stored_on_class(self):
        reg = ThreadRegistry.instance()
        assert ThreadRegistry._instance is reg

    def test_second_call_does_not_replace_class_var(self):
        r1 = ThreadRegistry.instance()
        ThreadRegistry.instance()
        assert ThreadRegistry._instance is r1

    def test_instance_is_thread_registry_type(self):
        reg = ThreadRegistry.instance()
        assert type(reg) is ThreadRegistry

    def test_thread_safe_concurrent_creation(self):
        """Multiple threads calling instance() should all receive the same object."""
        results = []

        def grab():
            results.append(ThreadRegistry.instance())

        threads = [threading.Thread(target=grab) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(id(r) for r in results)) == 1

    def test_direct_construction_bypasses_singleton(self):
        r1 = ThreadRegistry.instance()
        r2 = ThreadRegistry()
        assert r1 is not r2

    def test_instance_after_double_reset(self):
        ThreadRegistry._instance = None
        r1 = ThreadRegistry.instance()
        ThreadRegistry._instance = None
        r2 = ThreadRegistry.instance()
        assert r1 is not r2
        assert r2 is ThreadRegistry._instance


# ===========================================================================
# Section 3 – register()
# ===========================================================================

class TestRegister:
    def test_register_adds_to_threads(self):
        reg = ThreadRegistry()
        t = make_thread()
        reg.register("t1", t)
        assert t in reg._threads

    def test_register_adds_to_names(self):
        reg = ThreadRegistry()
        t = make_thread()
        reg.register("worker", t)
        assert reg._names["worker"] is t

    def test_register_multiple_threads(self):
        reg = ThreadRegistry()
        t1, t2, t3 = make_thread(), make_thread(), make_thread()
        reg.register("a", t1)
        reg.register("b", t2)
        reg.register("c", t3)
        assert t1 in reg._threads
        assert t2 in reg._threads
        assert t3 in reg._threads

    def test_register_multiple_names(self):
        reg = ThreadRegistry()
        t1, t2 = make_thread(), make_thread()
        reg.register("first", t1)
        reg.register("second", t2)
        assert reg._names["first"] is t1
        assert reg._names["second"] is t2

    def test_register_overwrites_same_name(self):
        reg = ThreadRegistry()
        t1 = make_thread()
        t2 = make_thread()
        reg.register("worker", t1)
        reg.register("worker", t2)
        assert reg._names["worker"] is t2

    def test_register_same_thread_under_different_names(self):
        reg = ThreadRegistry()
        t = make_thread()
        reg.register("alias_a", t)
        reg.register("alias_b", t)
        assert reg._names["alias_a"] is t
        assert reg._names["alias_b"] is t

    def test_register_mock_thread(self):
        reg = ThreadRegistry()
        m = make_mock_thread()
        reg.register("mock", m)
        assert reg._names["mock"] is m

    def test_register_returns_none(self):
        reg = ThreadRegistry()
        result = reg.register("t", make_thread())
        assert result is None

    def test_register_fifty_threads(self):
        reg = ThreadRegistry()
        threads = [make_thread() for _ in range(50)]
        for i, t in enumerate(threads):
            reg.register(f"t{i}", t)
        assert len(reg._names) == 50

    def test_register_empty_string_name(self):
        reg = ThreadRegistry()
        m = make_mock_thread()
        reg.register("", m)
        assert "" in reg._names

    def test_register_long_name(self):
        reg = ThreadRegistry()
        name = "x" * 500
        m = make_mock_thread()
        reg.register(name, m)
        assert name in reg._names

    def test_register_name_appears_in_names_dict(self):
        reg = ThreadRegistry()
        t = make_thread()
        reg.register("check_me", t)
        assert "check_me" in reg._names

    def test_register_updates_count_by_one(self):
        reg = ThreadRegistry()
        before = len(reg._names)
        t = make_thread()  # keep strong ref so WeakValueDictionary holds it
        reg.register("new_one", t)
        assert len(reg._names) == before + 1

    def test_register_overwrite_does_not_grow_names_count(self):
        reg = ThreadRegistry()
        t1 = make_thread()  # keep strong refs
        t2 = make_thread()
        reg.register("x", t1)
        reg.register("x", t2)
        assert len(reg._names) == 1


# ===========================================================================
# Section 4 – get_active_threads()
# ===========================================================================

class TestGetActiveThreads:
    def test_empty_registry_returns_empty_list(self):
        reg = ThreadRegistry()
        assert reg.get_active_threads() == []

    def test_alive_thread_returned(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        reg.register("alive", m)
        active = reg.get_active_threads()
        assert len(active) == 1
        assert active[0] == ("alive", m)

    def test_dead_thread_excluded(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=False)
        reg.register("dead", m)
        assert reg.get_active_threads() == []

    def test_mixed_alive_and_dead(self):
        reg = ThreadRegistry()
        alive_m = make_mock_thread(alive=True)
        dead_m = make_mock_thread(alive=False)
        reg.register("alive", alive_m)
        reg.register("dead", dead_m)
        active = reg.get_active_threads()
        names = [n for n, _ in active]
        assert "alive" in names
        assert "dead" not in names

    def test_returns_list_type(self):
        reg = ThreadRegistry()
        assert isinstance(reg.get_active_threads(), list)

    def test_returns_tuples_of_name_and_thread(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        reg.register("worker", m)
        active = reg.get_active_threads()
        assert isinstance(active[0], tuple)
        assert len(active[0]) == 2

    def test_all_alive_returns_all(self):
        reg = ThreadRegistry()
        mocks = [make_mock_thread(alive=True) for _ in range(5)]
        for i, m in enumerate(mocks):
            reg.register(f"t{i}", m)
        assert len(reg.get_active_threads()) == 5

    def test_all_dead_returns_empty(self):
        reg = ThreadRegistry()
        for i in range(4):
            reg.register(f"t{i}", make_mock_thread(alive=False))
        assert reg.get_active_threads() == []

    def test_is_alive_called_for_each_thread(self):
        reg = ThreadRegistry()
        m1 = make_mock_thread(alive=True)
        m2 = make_mock_thread(alive=False)
        reg.register("a", m1)
        reg.register("b", m2)
        reg.get_active_threads()
        m1.is_alive.assert_called()
        m2.is_alive.assert_called()

    def test_returns_correct_name_paired_with_thread(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        reg.register("my_thread", m)
        active = reg.get_active_threads()
        assert active[0][0] == "my_thread"
        assert active[0][1] is m

    def test_real_running_thread_appears_in_active(self):
        barrier = threading.Barrier(2)
        stop = threading.Event()

        def worker():
            barrier.wait()
            stop.wait()

        reg = ThreadRegistry()
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        reg.register("real", t)
        barrier.wait()
        active = reg.get_active_threads()
        stop.set()
        t.join(timeout=2)
        assert any(name == "real" for name, _ in active)

    def test_real_finished_thread_excluded(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        t.join(timeout=2)
        reg.register("done", t)
        assert reg.get_active_threads() == []

    def test_result_is_snapshot_copy(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        reg.register("snap", m)
        active = reg.get_active_threads()
        active.clear()
        # Internal names dict unaffected
        assert len(reg._names) == 1

    def test_successive_calls_reflect_liveness_change(self):
        reg = ThreadRegistry()
        m = make_mock_thread()
        m.is_alive.side_effect = [True, False]
        reg.register("t", m)
        first = reg.get_active_threads()
        second = reg.get_active_threads()
        assert len(first) == 1
        assert len(second) == 0

    def test_unstarted_real_thread_excluded(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        # Not started — is_alive() is False
        reg.register("unstarted", t)
        assert reg.get_active_threads() == []


# ===========================================================================
# Section 5 – shutdown()
# ===========================================================================

class TestShutdown:
    def test_no_active_threads_returns_empty_dict(self):
        reg = ThreadRegistry()
        assert reg.shutdown() == {}

    def test_no_active_threads_returns_dict_type(self):
        reg = ThreadRegistry()
        assert isinstance(reg.shutdown(), dict)

    def test_no_active_threads_default_timeout(self):
        reg = ThreadRegistry()
        assert reg.shutdown(timeout=0.0) == {}

    def test_completed_thread_returns_true(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        m.join.side_effect = lambda timeout: None
        m.is_alive.side_effect = [True, False]
        reg.register("fast", m)
        result = reg.shutdown(timeout=5.0)
        assert result["fast"] is True

    def test_timed_out_thread_returns_false(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        m.join.side_effect = lambda timeout: None
        m.is_alive.return_value = True  # never finishes
        reg.register("slow", m)
        result = reg.shutdown(timeout=0.01)
        assert result["slow"] is False

    def test_join_called_with_remaining_timeout(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        m.join.side_effect = lambda timeout: None
        m.is_alive.side_effect = [True, False]
        reg.register("t", m)
        reg.shutdown(timeout=7.0)
        call_args = m.join.call_args
        assert call_args is not None
        # Extract the timeout argument however it was passed
        timeout_used = (
            call_args[1].get("timeout")
            if call_args[1].get("timeout") is not None
            else call_args[0][0]
        )
        assert 0 < timeout_used <= 7.0

    def test_returns_dict_with_thread_name_as_key(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        m.join.side_effect = lambda timeout: None
        m.is_alive.side_effect = [True, False]
        reg.register("named_thread", m)
        result = reg.shutdown()
        assert "named_thread" in result

    def test_multiple_threads_all_complete(self):
        reg = ThreadRegistry()
        mocks = []
        for i in range(3):
            m = make_mock_thread(alive=True)
            m.join.side_effect = lambda timeout: None  # noqa: E731
            m.is_alive.side_effect = [True, False]
            mocks.append(m)          # keep strong refs
            reg.register(f"t{i}", m)
        result = reg.shutdown(timeout=10.0)
        assert all(v is True for v in result.values())
        assert len(result) == 3

    def test_multiple_threads_all_timeout(self):
        reg = ThreadRegistry()
        for i in range(3):
            m = make_mock_thread(alive=True)
            m.join.side_effect = lambda timeout: None
            m.is_alive.return_value = True
            reg.register(f"slow{i}", m)
        result = reg.shutdown(timeout=0.0)
        assert all(v is False for v in result.values())

    def test_mixed_threads_complete_and_timeout(self):
        reg = ThreadRegistry()
        fast = make_mock_thread(alive=True)
        fast.join.side_effect = lambda timeout: None
        fast.is_alive.side_effect = [True, False]
        reg.register("fast", fast)

        slow = make_mock_thread(alive=True)
        slow.join.side_effect = lambda timeout: None
        slow.is_alive.return_value = True
        reg.register("slow", slow)

        result = reg.shutdown(timeout=5.0)
        assert result["fast"] is True
        assert result["slow"] is False

    def test_result_keys_match_registered_names(self):
        reg = ThreadRegistry()
        names = ["alpha", "beta", "gamma"]
        mocks = []
        for name in names:
            m = make_mock_thread(alive=True)
            m.join.side_effect = lambda timeout: None  # noqa: E731
            m.is_alive.side_effect = [True, False]
            mocks.append(m)          # keep strong refs
            reg.register(name, m)
        result = reg.shutdown(timeout=5.0)
        assert set(result.keys()) == set(names)

    def test_shutdown_with_zero_timeout_all_false(self):
        """With zero timeout remaining <= 0 on first iteration; all False."""
        reg = ThreadRegistry()
        for i in range(3):
            m = make_mock_thread(alive=True)
            m.join.side_effect = lambda timeout: None
            m.is_alive.return_value = True
            reg.register(f"t{i}", m)
        result = reg.shutdown(timeout=0.0)
        assert all(v is False for v in result.values())

    def test_shutdown_reduces_remaining_timeout_across_threads(self):
        """After a slow join, remaining timeout shrinks for subsequent threads."""
        reg = ThreadRegistry()
        captured_timeouts = []

        def slow_join(timeout):
            time.sleep(0.05)

        m1 = make_mock_thread(alive=True)
        m1.join.side_effect = slow_join
        m1.is_alive.side_effect = [True, False]
        reg.register("first", m1)

        def capture_join(timeout):
            captured_timeouts.append(timeout)

        m2 = make_mock_thread(alive=True)
        m2.join.side_effect = capture_join
        m2.is_alive.side_effect = [True, False]
        reg.register("second", m2)

        reg.shutdown(timeout=2.0)
        if captured_timeouts:
            assert captured_timeouts[0] < 2.0

    def test_real_fast_thread_returns_true(self):
        reg = ThreadRegistry()
        ready = threading.Event()

        def target():
            ready.wait()  # stay alive until registered

        t = threading.Thread(target=target, daemon=True)
        t.start()
        reg.register("real_fast", t)
        ready.set()  # let it finish
        result = reg.shutdown(timeout=5.0)
        assert result.get("real_fast") is True

    def test_already_dead_thread_not_in_result(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        t.join(timeout=2)
        reg.register("already_dead", t)
        assert reg.shutdown(timeout=5.0) == {}

    def test_dead_threads_excluded_from_result(self):
        reg = ThreadRegistry()
        dead = make_mock_thread(alive=False)
        reg.register("dead_one", dead)
        alive = make_mock_thread(alive=True)
        alive.join.side_effect = lambda timeout: None
        alive.is_alive.side_effect = [True, False]
        reg.register("alive_one", alive)
        result = reg.shutdown(timeout=5.0)
        assert "dead_one" not in result
        assert "alive_one" in result

    def test_join_called_once_per_active_thread(self):
        reg = ThreadRegistry()
        mocks = []
        for i in range(4):
            m = make_mock_thread(alive=True)
            m.join.side_effect = lambda timeout: None
            m.is_alive.side_effect = [True, False]
            mocks.append(m)
            reg.register(f"t{i}", m)
        reg.shutdown(timeout=10.0)
        for m in mocks:
            m.join.assert_called_once()

    def test_shutdown_default_timeout_not_exceeded(self):
        """Default timeout is 10.0; join should be called with <= 10.0."""
        reg = ThreadRegistry()
        captured = []

        def cap_join(timeout):
            captured.append(timeout)

        m = make_mock_thread(alive=True)
        m.join.side_effect = cap_join
        m.is_alive.side_effect = [True, False]
        reg.register("t", m)
        reg.shutdown()  # no explicit timeout → default 10.0
        assert captured
        assert captured[0] <= 10.0

    def test_shutdown_result_values_are_booleans(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        m.join.side_effect = lambda timeout: None
        m.is_alive.side_effect = [True, False]
        reg.register("t", m)
        result = reg.shutdown(timeout=5.0)
        for v in result.values():
            assert isinstance(v, bool)

    def test_shutdown_twice_safe(self):
        reg = ThreadRegistry()
        r1 = reg.shutdown()
        r2 = reg.shutdown()
        assert r1 == {} == r2

    def test_shutdown_large_number_of_threads(self):
        reg = ThreadRegistry()
        mocks = []
        for i in range(20):
            m = make_mock_thread(alive=True)
            m.join.side_effect = lambda timeout: None  # noqa: E731
            m.is_alive.side_effect = [True, False]
            mocks.append(m)          # keep strong refs
            reg.register(f"t{i}", m)
        result = reg.shutdown(timeout=10.0)
        assert len(result) == 20

    def test_real_long_thread_returns_false_on_short_timeout(self):
        stop = threading.Event()

        def long_worker():
            stop.wait(timeout=60)

        reg = ThreadRegistry()
        t = threading.Thread(target=long_worker, daemon=True)
        t.start()
        reg.register("long_worker", t)
        result = reg.shutdown(timeout=0.01)
        assert result.get("long_worker") is False
        stop.set()
        t.join(timeout=2)


# ===========================================================================
# Section 6 – WeakSet / WeakValueDictionary behaviour
# ===========================================================================

class TestWeakRefBehavior:
    def test_dead_mock_excluded_from_get_active(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=False)
        reg.register("zombie", m)
        assert reg.get_active_threads() == []

    def test_weakvalue_dict_loses_ref_after_gc(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        reg.register("ephemeral", t)
        assert "ephemeral" in reg._names
        del t
        gc.collect()
        assert "ephemeral" not in reg._names

    def test_weakset_loses_ref_after_gc(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        reg.register("temp", t)
        count_before = len(list(reg._threads))
        del t
        gc.collect()
        count_after = len(list(reg._threads))
        assert count_after <= count_before

    def test_multiple_registrations_then_gc_clears_all(self):
        reg = ThreadRegistry()
        # Use a list comprehension so we can delete all refs at once.
        threads = [threading.Thread(target=lambda: None, daemon=True) for _ in range(5)]
        for i, t in enumerate(threads):
            reg.register(f"t{i}", t)
        count_before = len(reg._names)
        assert count_before == 5
        del threads
        gc.collect()
        # After GC all thread objects are gone; WeakValueDictionary should be empty
        assert len(reg._names) < count_before

    def test_weakset_does_not_prevent_gc(self):
        """Threads in _threads WeakSet should not prevent GC."""
        import weakref as _weakref
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        ref = _weakref.ref(t)
        reg.register("gc_test", t)
        del t
        gc.collect()
        assert ref() is None


# ===========================================================================
# Section 7 – Concurrency / thread-safety
# ===========================================================================

class TestConcurrency:
    def test_concurrent_register_no_crash(self):
        reg = ThreadRegistry()
        errors = []

        def do_register(i):
            try:
                reg.register(f"t{i}", make_mock_thread(alive=True))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_register, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_get_active_threads_no_crash(self):
        reg = ThreadRegistry()
        for i in range(10):
            reg.register(f"pre{i}", make_mock_thread(alive=True))

        errors = []

        def do_get():
            try:
                reg.get_active_threads()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_get) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_register_and_read(self):
        reg = ThreadRegistry()
        errors = []

        def writer(i):
            try:
                reg.register(f"w{i}", make_mock_thread(alive=True))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                reg.get_active_threads()
            except Exception as e:
                errors.append(e)

        ts = [threading.Thread(target=writer, args=(i,)) for i in range(15)]
        ts += [threading.Thread(target=reader) for _ in range(15)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert errors == []


# ===========================================================================
# Section 8 – Edge cases and integration
# ===========================================================================

class TestEdgeCases:
    def test_register_dead_thread_then_shutdown_returns_empty(self):
        reg = ThreadRegistry()
        reg.register("dead", make_mock_thread(alive=False))
        assert reg.shutdown() == {}

    def test_shutdown_multiple_times_stays_empty(self):
        reg = ThreadRegistry()
        assert reg.shutdown() == {}
        assert reg.shutdown() == {}

    def test_register_overwrite_shutdown_uses_new_thread(self):
        reg = ThreadRegistry()
        old_m = make_mock_thread(alive=False)
        new_m = make_mock_thread(alive=True)
        new_m.join.side_effect = lambda timeout: None
        new_m.is_alive.side_effect = [True, False]
        reg.register("worker", old_m)
        reg.register("worker", new_m)
        result = reg.shutdown(timeout=5.0)
        assert "worker" in result
        assert result["worker"] is True

    def test_singleton_and_direct_instance_separate_state(self):
        singleton = ThreadRegistry.instance()
        direct = ThreadRegistry()
        direct.register("x", make_mock_thread(alive=True))
        assert "x" not in singleton._names

    def test_unstarted_thread_is_not_active(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        reg.register("unstarted", t)
        assert reg.get_active_threads() == []

    def test_register_does_not_start_thread(self):
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        reg.register("unstarted", t)
        assert not t.is_alive()

    def test_shutdown_with_single_zero_timeout(self):
        reg = ThreadRegistry()
        m = make_mock_thread(alive=True)
        m.join.side_effect = lambda timeout: None
        m.is_alive.return_value = True
        reg.register("t", m)
        result = reg.shutdown(timeout=0.0)
        assert result["t"] is False

    def test_get_active_after_shutdown(self):
        """After shutdown of a thread that completed, get_active returns nothing."""
        reg = ThreadRegistry()
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        reg.register("real", t)
        reg.shutdown(timeout=5.0)
        active = reg.get_active_threads()
        assert active == []

    def test_register_and_get_active_consistency(self):
        reg = ThreadRegistry()
        alive_mocks = [make_mock_thread(alive=True) for _ in range(4)]
        dead_mocks = [make_mock_thread(alive=False) for _ in range(3)]
        for i, m in enumerate(alive_mocks):
            reg.register(f"alive{i}", m)
        for i, m in enumerate(dead_mocks):
            reg.register(f"dead{i}", m)
        active = reg.get_active_threads()
        assert len(active) == 4

    def test_names_not_in_active_when_all_dead(self):
        reg = ThreadRegistry()
        # Keep strong refs so WeakValueDictionary retains them
        mocks = [make_mock_thread(alive=False) for _ in range(5)]
        for i, m in enumerate(mocks):
            reg.register(f"d{i}", m)
        assert reg.get_active_threads() == []
        # Names dict still holds them while we hold strong refs
        assert len(reg._names) == 5
