"""
Safe UI Update Helper - Thread-safe UI updates with winfo_exists() protection.

Wraps tkinter's .after() to prevent TclError crashes when widgets
are destroyed during shutdown while worker threads are still running.
"""

from utils.structured_logging import get_logger

logger = get_logger(__name__)


def schedule_ui_update(widget, callback, *args):
    """Schedule a UI update from a worker thread, safely.

    Checks that the widget still exists before invoking the callback.
    Silently drops the update if the widget has been destroyed.

    Args:
        widget: Any tkinter widget with .after() and .winfo_exists()
        callback: Function to call on the main thread
        *args: Arguments to pass to callback
    """
    def _safe():
        try:
            if widget.winfo_exists():
                callback(*args)
        except Exception:
            pass  # Widget destroyed between check and call

    try:
        widget.after(0, _safe)
    except Exception:
        pass  # Widget already destroyed, can't schedule
