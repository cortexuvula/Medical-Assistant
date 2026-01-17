"""
UI Notification Handler

Centralized notification system for the application.
Provides a consistent interface for displaying messages to users,
with support for different notification types and future extensibility.
"""

from tkinter import messagebox
from typing import Optional, Callable, Any
from enum import Enum
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class NotificationType(Enum):
    """Types of notifications supported by the handler."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CONFIRM = "confirm"


class UINotificationHandler:
    """Centralized handler for all UI notifications.

    This class provides a unified interface for displaying notifications,
    allowing for consistent styling and future extensibility (e.g., toast
    notifications, logging, analytics).

    Usage:
        from ui.notification_handler import notify

        # Show info message
        notify.info("Settings Saved", "Your settings have been saved successfully.")

        # Show error
        notify.error("Error", "Failed to save file.")

        # Ask for confirmation
        if notify.confirm("Delete", "Are you sure you want to delete this item?"):
            # User confirmed
            pass
    """

    def __init__(self):
        """Initialize the notification handler."""
        self._default_parent = None
        self._log_notifications = True
        self._custom_handlers: dict[NotificationType, Callable] = {}

    def set_default_parent(self, parent) -> None:
        """Set the default parent window for dialogs.

        Args:
            parent: The default parent window to use for dialogs
        """
        self._default_parent = parent

    def set_logging(self, enabled: bool) -> None:
        """Enable or disable notification logging.

        Args:
            enabled: Whether to log notifications
        """
        self._log_notifications = enabled

    def register_handler(
        self,
        notification_type: NotificationType,
        handler: Callable
    ) -> None:
        """Register a custom handler for a notification type.

        This allows for custom notification implementations (e.g., toast
        notifications instead of modal dialogs).

        Args:
            notification_type: The type of notification to handle
            handler: Callable that takes (title, message, parent) and returns result
        """
        self._custom_handlers[notification_type] = handler

    def _log(self, level: str, title: str, message: str) -> None:
        """Log a notification if logging is enabled."""
        if self._log_notifications:
            log_func = getattr(logger, level, logger.info)
            log_func(f"[{title}] {message}")

    def info(
        self,
        title: str,
        message: str,
        parent: Optional[Any] = None
    ) -> None:
        """Show an informational message.

        Args:
            title: Dialog title
            message: Message to display
            parent: Optional parent window (uses default if not provided)
        """
        self._log("info", title, message)

        if NotificationType.INFO in self._custom_handlers:
            self._custom_handlers[NotificationType.INFO](title, message, parent)
            return

        kwargs = {"title": title, "message": message}
        if parent or self._default_parent:
            kwargs["parent"] = parent or self._default_parent
        messagebox.showinfo(**kwargs)

    def success(
        self,
        title: str,
        message: str,
        parent: Optional[Any] = None
    ) -> None:
        """Show a success message.

        Args:
            title: Dialog title
            message: Message to display
            parent: Optional parent window
        """
        self._log("info", title, message)

        if NotificationType.SUCCESS in self._custom_handlers:
            self._custom_handlers[NotificationType.SUCCESS](title, message, parent)
            return

        # Success uses showinfo with a success-style title
        kwargs = {"title": title, "message": message}
        if parent or self._default_parent:
            kwargs["parent"] = parent or self._default_parent
        messagebox.showinfo(**kwargs)

    def warning(
        self,
        title: str,
        message: str,
        parent: Optional[Any] = None
    ) -> None:
        """Show a warning message.

        Args:
            title: Dialog title
            message: Message to display
            parent: Optional parent window
        """
        self._log("warning", title, message)

        if NotificationType.WARNING in self._custom_handlers:
            self._custom_handlers[NotificationType.WARNING](title, message, parent)
            return

        kwargs = {"title": title, "message": message}
        if parent or self._default_parent:
            kwargs["parent"] = parent or self._default_parent
        messagebox.showwarning(**kwargs)

    def error(
        self,
        title: str,
        message: str,
        parent: Optional[Any] = None,
        exception: Optional[Exception] = None
    ) -> None:
        """Show an error message.

        Args:
            title: Dialog title
            message: Message to display
            parent: Optional parent window
            exception: Optional exception to log (not shown to user)
        """
        if exception:
            logger.error(f"[{title}] {message}", exc_info=exception)
        else:
            self._log("error", title, message)

        if NotificationType.ERROR in self._custom_handlers:
            self._custom_handlers[NotificationType.ERROR](title, message, parent)
            return

        kwargs = {"title": title, "message": message}
        if parent or self._default_parent:
            kwargs["parent"] = parent or self._default_parent
        messagebox.showerror(**kwargs)

    def confirm(
        self,
        title: str,
        message: str,
        parent: Optional[Any] = None
    ) -> bool:
        """Show a confirmation dialog and return user's choice.

        Args:
            title: Dialog title
            message: Message to display
            parent: Optional parent window

        Returns:
            True if user confirmed, False otherwise
        """
        self._log("info", title, f"[CONFIRM] {message}")

        if NotificationType.CONFIRM in self._custom_handlers:
            return self._custom_handlers[NotificationType.CONFIRM](title, message, parent)

        kwargs = {"title": title, "message": message}
        if parent or self._default_parent:
            kwargs["parent"] = parent or self._default_parent
        return messagebox.askyesno(**kwargs)

    def ask_yes_no_cancel(
        self,
        title: str,
        message: str,
        parent: Optional[Any] = None
    ) -> Optional[bool]:
        """Show a yes/no/cancel dialog.

        Args:
            title: Dialog title
            message: Message to display
            parent: Optional parent window

        Returns:
            True for Yes, False for No, None for Cancel
        """
        self._log("info", title, f"[YES/NO/CANCEL] {message}")

        kwargs = {"title": title, "message": message}
        if parent or self._default_parent:
            kwargs["parent"] = parent or self._default_parent
        return messagebox.askyesnocancel(**kwargs)


# Global instance for easy access
notify = UINotificationHandler()


# Convenience functions for backward compatibility and ease of use
def show_info(title: str, message: str, parent=None) -> None:
    """Show an informational message."""
    notify.info(title, message, parent)


def show_success(title: str, message: str, parent=None) -> None:
    """Show a success message."""
    notify.success(title, message, parent)


def show_warning(title: str, message: str, parent=None) -> None:
    """Show a warning message."""
    notify.warning(title, message, parent)


def show_error(title: str, message: str, parent=None, exception=None) -> None:
    """Show an error message."""
    notify.error(title, message, parent, exception)


def ask_confirm(title: str, message: str, parent=None) -> bool:
    """Show a confirmation dialog and return user's choice."""
    return notify.confirm(title, message, parent)


__all__ = [
    "UINotificationHandler",
    "NotificationType",
    "notify",
    "show_info",
    "show_success",
    "show_warning",
    "show_error",
    "ask_confirm",
]
