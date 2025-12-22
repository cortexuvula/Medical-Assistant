"""
Thread Safety Tests for Manager Singletons

Tests that global singleton managers are thread-safe and properly
implement double-checked locking pattern.
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTranslationManagerThreadSafety:
    """Test thread safety of TranslationManager singleton."""

    def test_singleton_returns_same_instance(self):
        """Test that get_translation_manager always returns the same instance."""
        # Reset the global instance for testing
        import src.managers.translation_manager as tm
        tm._translation_manager = None

        with patch.object(tm.TranslationManager, '__init__', return_value=None):
            manager1 = tm.get_translation_manager()
            manager2 = tm.get_translation_manager()

            assert manager1 is manager2, "Should return the same instance"

    def test_concurrent_initialization(self):
        """Test that concurrent calls create only one instance."""
        import src.managers.translation_manager as tm

        # Reset the global instance
        tm._translation_manager = None

        instances: List[tm.TranslationManager] = []
        errors: List[Exception] = []
        lock = threading.Lock()

        def get_manager():
            try:
                with patch.object(tm.TranslationManager, '__init__', return_value=None):
                    manager = tm.get_translation_manager()
                    with lock:
                        instances.append(manager)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Create multiple threads that all try to get the manager simultaneously
        threads = [threading.Thread(target=get_manager) for _ in range(20)]

        # Start all threads at approximately the same time
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(instances) == 20, "All threads should have gotten an instance"

        # All instances should be the same object
        unique_instances = set(id(inst) for inst in instances)
        assert len(unique_instances) == 1, "All threads should get the same instance"

    def test_no_race_condition_on_init(self):
        """Test that initialization happens exactly once even under contention."""
        import src.managers.translation_manager as tm

        init_count = [0]
        original_init = tm.TranslationManager.__init__

        def counting_init(self):
            init_count[0] += 1
            # Simulate slow initialization
            time.sleep(0.01)
            # Don't call original_init to avoid actual initialization

        # Reset the global instance
        tm._translation_manager = None

        with patch.object(tm.TranslationManager, '__init__', counting_init):
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(tm.get_translation_manager) for _ in range(50)]
                for future in as_completed(futures):
                    future.result()  # Wait for completion

        # TranslationManager.__init__ should only be called once
        assert init_count[0] == 1, f"Init was called {init_count[0]} times, expected 1"


class TestTTSManagerThreadSafety:
    """Test thread safety of TTSManager singleton."""

    def test_singleton_returns_same_instance(self):
        """Test that get_tts_manager always returns the same instance."""
        import src.managers.tts_manager as tts

        # Reset the global instance
        tts._tts_manager = None

        with patch.object(tts.TTSManager, '__init__', return_value=None):
            manager1 = tts.get_tts_manager()
            manager2 = tts.get_tts_manager()

            assert manager1 is manager2, "Should return the same instance"

    def test_concurrent_initialization(self):
        """Test that concurrent calls create only one instance."""
        import src.managers.tts_manager as tts

        # Reset the global instance
        tts._tts_manager = None

        instances: List[tts.TTSManager] = []
        lock = threading.Lock()

        def get_manager():
            with patch.object(tts.TTSManager, '__init__', return_value=None):
                manager = tts.get_tts_manager()
                with lock:
                    instances.append(manager)

        threads = [threading.Thread(target=get_manager) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same object
        unique_instances = set(id(inst) for inst in instances)
        assert len(unique_instances) == 1, "All threads should get the same instance"

    def test_no_race_condition_on_init(self):
        """Test that initialization happens exactly once."""
        import src.managers.tts_manager as tts

        init_count = [0]

        def counting_init(self):
            init_count[0] += 1
            time.sleep(0.01)

        tts._tts_manager = None

        with patch.object(tts.TTSManager, '__init__', counting_init):
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(tts.get_tts_manager) for _ in range(50)]
                for future in as_completed(futures):
                    future.result()

        assert init_count[0] == 1, f"Init was called {init_count[0]} times, expected 1"


class TestModelProviderThreadSafety:
    """Test thread safety of ModelProvider (module-level instantiation)."""

    def test_module_level_instance_is_singleton(self):
        """Test that module-level model_provider is a singleton."""
        from src.ai import model_provider as mp

        # Module-level instantiation should always return the same instance
        provider1 = mp.model_provider
        provider2 = mp.model_provider

        assert provider1 is provider2, "Should be the same instance"

    def test_cache_is_thread_safe(self):
        """Test that the LRU cache is thread-safe."""
        from src.ai.model_provider import LRUCache

        cache = LRUCache(max_size=100, ttl_seconds=3600)
        errors: List[Exception] = []

        def cache_operations(thread_id: int):
            try:
                for i in range(100):
                    key = f"key_{thread_id}_{i}"
                    cache.set(key, f"value_{thread_id}_{i}")
                    _ = cache.get(key)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(cache_operations, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Cache operations had errors: {errors}"


class TestTypedConfigsThreadSafety:
    """Test that typed config dataclasses are thread-safe."""

    def test_batch_processing_options_concurrent_creation(self):
        """Test concurrent creation of BatchProcessingOptions."""
        from src.types.configs import BatchProcessingOptions, Priority

        options_list: List[BatchProcessingOptions] = []
        lock = threading.Lock()

        def create_options(thread_id: int):
            for i in range(10):
                opts = BatchProcessingOptions(
                    generate_soap=True,
                    priority=Priority.HIGH,
                    max_concurrent=thread_id
                )
                with lock:
                    options_list.append(opts)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_options, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        assert len(options_list) == 100, "All options should be created"

    def test_config_to_dict_thread_safe(self):
        """Test that to_dict is thread-safe."""
        from src.types.configs import AgentExecutionOptions

        options = AgentExecutionOptions(timeout=30, max_retries=5)
        results: List[dict] = []
        lock = threading.Lock()

        def convert_to_dict():
            for _ in range(100):
                d = options.to_dict()
                with lock:
                    results.append(d)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(convert_to_dict) for _ in range(10)]
            for future in as_completed(futures):
                future.result()

        # All conversions should produce the same result
        assert all(r == results[0] for r in results), "All to_dict results should be identical"


class TestDoubleCheckedLockingPattern:
    """Test the double-checked locking pattern implementation."""

    def test_first_check_fast_path(self):
        """Test that subsequent calls don't acquire the lock."""
        import src.managers.translation_manager as tm

        # Reset and initialize once
        tm._translation_manager = None

        with patch.object(tm.TranslationManager, '__init__', return_value=None):
            # First call initializes
            _ = tm.get_translation_manager()

            # Verify the instance is set
            assert tm._translation_manager is not None

            # Mock the lock to track if it's acquired
            original_lock = tm._translation_manager_lock
            lock_acquired = [False]

            class TrackingLock:
                def __enter__(self):
                    lock_acquired[0] = True
                    return original_lock.__enter__()

                def __exit__(self, *args):
                    return original_lock.__exit__(*args)

            tm._translation_manager_lock = TrackingLock()

            # Second call should use fast path (no lock)
            _ = tm.get_translation_manager()

            # Lock should NOT have been acquired
            assert not lock_acquired[0], "Lock should not be acquired on fast path"

            # Restore original lock
            tm._translation_manager_lock = original_lock


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton instances before each test."""
    import src.managers.translation_manager as tm
    import src.managers.tts_manager as tts

    # Store original values
    original_tm = tm._translation_manager
    original_tts = tts._tts_manager

    # Reset before test
    tm._translation_manager = None
    tts._tts_manager = None

    yield

    # Restore after test (optional - depends on test isolation needs)
    tm._translation_manager = original_tm
    tts._tts_manager = original_tts
