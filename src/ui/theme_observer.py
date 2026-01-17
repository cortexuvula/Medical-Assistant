"""
Theme Observer Module

Implements an observer pattern for theme changes, allowing UI components
to automatically update when the theme changes.
"""

import weakref
from typing import Optional, Callable, Set, Protocol, runtime_checkable
from abc import abstractmethod
from utils.structured_logging import get_logger

from ui.ui_constants import Colors

logger = get_logger(__name__)


@runtime_checkable
class ThemeAware(Protocol):
    """Protocol for theme-aware components."""

    @abstractmethod
    def update_theme(self, is_dark: bool) -> None:
        """Update component for theme change.

        Args:
            is_dark: Whether dark mode is active
        """
        ...


class ThemeObserver:
    """Singleton observer for theme change notifications.

    This class manages theme change notifications using the observer pattern.
    Components can register to receive notifications when the theme changes.

    Usage:
        # Get the singleton instance
        observer = ThemeObserver.get_instance()

        # Register a component
        observer.register(my_component)

        # Notify all components of theme change
        observer.notify_theme_change(is_dark=True)

        # Unregister when done
        observer.unregister(my_component)
    """

    _instance: Optional['ThemeObserver'] = None

    def __init__(self):
        """Initialize the theme observer."""
        # Use weak references to avoid memory leaks
        self._observers: Set[weakref.ref] = set()
        self._callbacks: Set[weakref.ref] = set()
        self._is_dark: bool = False

    @classmethod
    def get_instance(cls) -> 'ThemeObserver':
        """Get the singleton instance.

        Returns:
            ThemeObserver singleton
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    @property
    def is_dark(self) -> bool:
        """Get current theme state."""
        return self._is_dark

    def register(self, component: ThemeAware) -> None:
        """Register a component to receive theme updates.

        Args:
            component: A ThemeAware component with update_theme method
        """
        # Create weak reference with cleanup callback
        ref = weakref.ref(component, self._remove_dead_ref)
        self._observers.add(ref)
        logging.debug(f"Registered theme observer: {type(component).__name__}")

    def register_callback(self, callback: Callable[[bool], None]) -> None:
        """Register a callback function for theme changes.

        Args:
            callback: Function that takes is_dark bool parameter
        """
        # For callbacks, we need to be careful with weak references
        # Only use weak references for bound methods
        try:
            ref = weakref.ref(callback, self._remove_dead_callback)
            self._callbacks.add(ref)
        except TypeError:
            # Function is not weak-referenceable (e.g., lambda)
            # Store it directly (be careful with memory)
            self._callbacks.add(callback)
        logging.debug(f"Registered theme callback")

    def unregister(self, component: ThemeAware) -> None:
        """Unregister a component from theme updates.

        Args:
            component: The component to unregister
        """
        # Find and remove the weak reference
        refs_to_remove = set()
        for ref in self._observers:
            if isinstance(ref, weakref.ref):
                obj = ref()
                if obj is component or obj is None:
                    refs_to_remove.add(ref)
            elif ref is component:
                refs_to_remove.add(ref)

        self._observers -= refs_to_remove
        logging.debug(f"Unregistered theme observer: {type(component).__name__}")

    def unregister_callback(self, callback: Callable[[bool], None]) -> None:
        """Unregister a callback function.

        Args:
            callback: The callback to unregister
        """
        refs_to_remove = set()
        for ref in self._callbacks:
            if isinstance(ref, weakref.ref):
                obj = ref()
                if obj is callback or obj is None:
                    refs_to_remove.add(ref)
            elif ref is callback:
                refs_to_remove.add(ref)

        self._callbacks -= refs_to_remove

    def _remove_dead_ref(self, ref: weakref.ref) -> None:
        """Remove a dead weak reference."""
        self._observers.discard(ref)

    def _remove_dead_callback(self, ref: weakref.ref) -> None:
        """Remove a dead callback reference."""
        self._callbacks.discard(ref)

    def notify_theme_change(self, is_dark: bool) -> None:
        """Notify all registered components of a theme change.

        Args:
            is_dark: Whether dark mode is now active
        """
        self._is_dark = is_dark
        colors = Colors.get_theme_colors(is_dark)

        logging.debug(f"Notifying theme change: is_dark={is_dark}")

        # Collect dead references
        dead_refs = set()

        # Notify observers
        for ref in self._observers.copy():
            if isinstance(ref, weakref.ref):
                component = ref()
                if component is not None:
                    try:
                        component.update_theme(is_dark)
                    except Exception as e:
                        logging.error(f"Error updating theme for {type(component).__name__}: {e}")
                else:
                    dead_refs.add(ref)

        # Notify callbacks
        for ref in self._callbacks.copy():
            if isinstance(ref, weakref.ref):
                callback = ref()
                if callback is not None:
                    try:
                        callback(is_dark)
                    except Exception as e:
                        logging.error(f"Error in theme callback: {e}")
                else:
                    dead_refs.add(ref)
            elif callable(ref):
                try:
                    ref(is_dark)
                except Exception as e:
                    logging.error(f"Error in theme callback: {e}")

        # Clean up dead references
        self._observers -= dead_refs
        self._callbacks -= dead_refs

    def get_observer_count(self) -> int:
        """Get the number of registered observers.

        Returns:
            Number of active observers
        """
        # Count only live references
        count = 0
        for ref in self._observers:
            if isinstance(ref, weakref.ref):
                if ref() is not None:
                    count += 1
            else:
                count += 1
        return count


class ThemeAwareMixin:
    """Mixin class to make widgets theme-aware.

    Inherit from this mixin to automatically register for theme updates.

    Usage:
        class MyWidget(ttk.Frame, ThemeAwareMixin):
            def __init__(self, parent):
                super().__init__(parent)
                self.init_theme_aware()

            def update_theme(self, is_dark: bool):
                # Update widget appearance
                pass
    """

    def init_theme_aware(self) -> None:
        """Initialize theme awareness. Call this in __init__."""
        observer = ThemeObserver.get_instance()
        observer.register(self)

        # Apply current theme
        self.update_theme(observer.is_dark)

    def cleanup_theme_aware(self) -> None:
        """Cleanup theme registration. Call this before destroying."""
        observer = ThemeObserver.get_instance()
        observer.unregister(self)

    def update_theme(self, is_dark: bool) -> None:
        """Update widget for theme change. Override in subclass."""
        pass


def theme_aware(cls):
    """Decorator to make a class theme-aware.

    Usage:
        @theme_aware
        class MyWidget(ttk.Frame):
            def update_theme(self, is_dark: bool):
                # Update widget appearance
                pass

    The decorated class will automatically register for theme updates.
    """
    original_init = cls.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        observer = ThemeObserver.get_instance()
        observer.register(self)

    cls.__init__ = new_init

    # Add update_theme method if not present
    if not hasattr(cls, 'update_theme'):
        def update_theme(self, is_dark: bool) -> None:
            pass
        cls.update_theme = update_theme

    return cls


# Convenience functions

def get_theme_observer() -> ThemeObserver:
    """Get the theme observer singleton."""
    return ThemeObserver.get_instance()


def register_for_theme_updates(component: ThemeAware) -> None:
    """Register a component for theme updates."""
    ThemeObserver.get_instance().register(component)


def unregister_from_theme_updates(component: ThemeAware) -> None:
    """Unregister a component from theme updates."""
    ThemeObserver.get_instance().unregister(component)


def on_theme_change(callback: Callable[[bool], None]) -> None:
    """Register a callback for theme changes."""
    ThemeObserver.get_instance().register_callback(callback)


def notify_theme_change(is_dark: bool) -> None:
    """Notify all components of a theme change."""
    ThemeObserver.get_instance().notify_theme_change(is_dark)
