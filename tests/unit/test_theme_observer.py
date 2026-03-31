"""
Tests for src/ui/theme_observer.py

Covers ThemeAware protocol; ThemeObserver (singleton, is_dark, register,
unregister, register_callback, notify_theme_change, get_observer_count);
ThemeAwareMixin; convenience functions (get_theme_observer,
register_for_theme_updates, on_theme_change, notify_theme_change).
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ui.theme_observer import (
    ThemeAware, ThemeObserver, ThemeAwareMixin,
    get_theme_observer, register_for_theme_updates,
    unregister_from_theme_updates, on_theme_change, notify_theme_change,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeComponent:
    """Minimal ThemeAware implementation."""
    def __init__(self):
        self.theme_calls = []

    def update_theme(self, is_dark: bool) -> None:
        self.theme_calls.append(is_dark)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    ThemeObserver.reset_instance()
    yield
    ThemeObserver.reset_instance()


# ===========================================================================
# ThemeAware protocol
# ===========================================================================

class TestThemeAwareProtocol:
    def test_fake_component_is_theme_aware(self):
        assert isinstance(_FakeComponent(), ThemeAware)

    def test_object_without_update_theme_not_theme_aware(self):
        class _Plain:
            pass
        assert not isinstance(_Plain(), ThemeAware)


# ===========================================================================
# ThemeObserver — singleton
# ===========================================================================

class TestThemeObserverSingleton:
    def test_get_instance_returns_observer(self):
        obs = ThemeObserver.get_instance()
        assert isinstance(obs, ThemeObserver)

    def test_same_instance_each_call(self):
        obs1 = ThemeObserver.get_instance()
        obs2 = ThemeObserver.get_instance()
        assert obs1 is obs2

    def test_reset_clears_singleton(self):
        obs1 = ThemeObserver.get_instance()
        ThemeObserver.reset_instance()
        obs2 = ThemeObserver.get_instance()
        assert obs1 is not obs2


# ===========================================================================
# ThemeObserver — is_dark
# ===========================================================================

class TestThemeObserverIsDark:
    def test_default_is_light(self):
        obs = ThemeObserver.get_instance()
        assert obs.is_dark is False

    def test_is_dark_after_notify_dark(self):
        obs = ThemeObserver.get_instance()
        obs.notify_theme_change(is_dark=True)
        assert obs.is_dark is True

    def test_is_light_after_notify_light(self):
        obs = ThemeObserver.get_instance()
        obs.notify_theme_change(is_dark=True)
        obs.notify_theme_change(is_dark=False)
        assert obs.is_dark is False


# ===========================================================================
# ThemeObserver — register / unregister
# ===========================================================================

class TestThemeObserverRegister:
    def test_register_increases_observer_count(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        obs.register(comp)
        assert obs.get_observer_count() == 1

    def test_register_multiple(self):
        obs = ThemeObserver.get_instance()
        c1, c2 = _FakeComponent(), _FakeComponent()
        obs.register(c1)
        obs.register(c2)
        assert obs.get_observer_count() == 2

    def test_unregister_decreases_count(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        obs.register(comp)
        obs.unregister(comp)
        assert obs.get_observer_count() == 0

    def test_unregister_unknown_no_error(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        obs.unregister(comp)  # Not registered — should not raise


# ===========================================================================
# ThemeObserver — notify_theme_change (observers)
# ===========================================================================

class TestThemeObserverNotify:
    def test_notify_calls_update_theme_on_component(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        obs.register(comp)
        obs.notify_theme_change(is_dark=True)
        assert True in comp.theme_calls

    def test_notify_passes_correct_value(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        obs.register(comp)
        obs.notify_theme_change(is_dark=False)
        assert comp.theme_calls[-1] is False

    def test_notify_calls_all_registered(self):
        obs = ThemeObserver.get_instance()
        c1, c2 = _FakeComponent(), _FakeComponent()
        obs.register(c1)
        obs.register(c2)
        obs.notify_theme_change(is_dark=True)
        assert len(c1.theme_calls) == 1
        assert len(c2.theme_calls) == 1

    def test_notify_no_observers_no_error(self):
        obs = ThemeObserver.get_instance()
        obs.notify_theme_change(is_dark=True)  # Should not raise

    def test_notify_after_unregister_not_called(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        obs.register(comp)
        obs.unregister(comp)
        obs.notify_theme_change(is_dark=True)
        assert comp.theme_calls == []

    def test_notify_exception_in_component_does_not_propagate(self):
        obs = ThemeObserver.get_instance()

        class _BadComp:
            def update_theme(self, is_dark): raise RuntimeError("bad")

        import weakref
        # Register directly as a weakref
        bad = _BadComp()
        obs.register(bad)
        obs.notify_theme_change(is_dark=True)  # Should not raise


# ===========================================================================
# ThemeObserver — register_callback / notify via callbacks
# ===========================================================================

class TestThemeObserverCallbacks:
    def test_callback_called_on_notify(self):
        obs = ThemeObserver.get_instance()
        received = []

        def cb(is_dark): received.append(is_dark)

        obs.register_callback(cb)
        obs.notify_theme_change(is_dark=True)
        assert True in received

    def test_callback_receives_correct_value(self):
        obs = ThemeObserver.get_instance()
        received = []

        def cb(v): received.append(v)  # named function keeps strong ref via closure

        obs.register_callback(cb)
        obs.notify_theme_change(is_dark=False)
        assert received[-1] is False

    def test_multiple_callbacks_all_called(self):
        obs = ThemeObserver.get_instance()
        counts = [0, 0]

        def cb1(_): counts[0] += 1
        def cb2(_): counts[1] += 1

        obs.register_callback(cb1)
        obs.register_callback(cb2)
        obs.notify_theme_change(is_dark=True)
        assert counts[0] == 1
        assert counts[1] == 1


# ===========================================================================
# ThemeObserver — get_observer_count
# ===========================================================================

class TestGetObserverCount:
    def test_zero_initially(self):
        obs = ThemeObserver.get_instance()
        assert obs.get_observer_count() == 0

    def test_increments_on_register(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()  # Must hold strong ref so weakref stays alive
        obs.register(comp)
        assert obs.get_observer_count() == 1


# ===========================================================================
# ThemeAwareMixin
# ===========================================================================

class TestThemeAwareMixin:
    def test_mixin_has_update_theme(self):
        mixin = ThemeAwareMixin()
        assert hasattr(mixin, "update_theme")

    def test_update_theme_no_error(self):
        mixin = ThemeAwareMixin()
        mixin.update_theme(True)  # Should not raise
        mixin.update_theme(False)


# ===========================================================================
# Convenience functions
# ===========================================================================

class TestConvenienceFunctions:
    def test_get_theme_observer_returns_observer(self):
        obs = get_theme_observer()
        assert isinstance(obs, ThemeObserver)

    def test_get_theme_observer_same_as_singleton(self):
        assert get_theme_observer() is ThemeObserver.get_instance()

    def test_register_for_theme_updates(self):
        comp = _FakeComponent()
        register_for_theme_updates(comp)
        obs = ThemeObserver.get_instance()
        assert obs.get_observer_count() >= 1

    def test_unregister_from_theme_updates(self):
        obs = ThemeObserver.get_instance()
        comp = _FakeComponent()
        register_for_theme_updates(comp)
        count_before = obs.get_observer_count()
        unregister_from_theme_updates(comp)
        assert obs.get_observer_count() == count_before - 1

    def test_on_theme_change_registers_callback(self):
        received = []

        def cb(v): received.append(v)  # named function keeps strong ref

        on_theme_change(cb)
        notify_theme_change(is_dark=True)
        assert True in received

    def test_notify_theme_change_updates_is_dark(self):
        notify_theme_change(is_dark=True)
        assert get_theme_observer().is_dark is True
