"""
Chat UI Mixin

Provides chat tab display, typing indicators, clipboard operations,
and context menu handling for ChatProcessor. Extracted to keep the
main processor focused on AI orchestration.
"""

import sqlite3
import tkinter as tk
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from ai.chat_processor import ToolInfo

logger = get_logger(__name__)


class ChatUIMixin:
    """UI and display methods for ChatProcessor."""

    def _show_ai_response(self, response: str):
        """Show a brief notification about the AI response."""
        def show_notification():
            try:
                logger.info(f"AI Response received: {response[:200]}{'...' if len(response) > 200 else ''}")
                self.app.status_manager.info("AI response processed and applied")
            except (tk.TclError, AttributeError) as e:
                logger.error(f"Error showing AI response notification: {e}")

        # Show on main thread
        self.app.after(0, show_notification)

    def _append_to_chat_tab(self, user_message: str, ai_response: str, tool_info: Optional['ToolInfo'] = None):
        """Append conversation to chat tab in ChatGPT style."""
        def append_chat():
            try:
                chat_widget = self.app.chat_text

                # Get current content to check if we need separator
                current_content = chat_widget.get("1.0", "end-1c")

                # Add separator if there's existing content
                if current_content.strip():
                    chat_widget.insert("end", "\n" + "="*50 + "\n\n")

                # Add timestamp
                timestamp = datetime.now().strftime("%H:%M:%S")
                chat_widget.insert("end", f"[{timestamp}]\n", "timestamp")

                # Add user message
                chat_widget.insert("end", f"User: {user_message}\n\n", "user")

                # Add tool usage info if present
                if tool_info and tool_info.get("tool_calls"):
                    chat_widget.insert("end", "Tools Used:\n", "tool_header")
                    for tool_call in tool_info["tool_calls"]:
                        chat_widget.insert("end", f"  \u2022 {tool_call.tool_name}", "tool_name")
                        if tool_call.arguments:
                            args_str = ", ".join(f"{k}={v}" for k, v in tool_call.arguments.items())
                            chat_widget.insert("end", f"({args_str})", "tool_args")
                        chat_widget.insert("end", "\n")
                    chat_widget.insert("end", "\n")

                # Add AI response with copy button
                chat_widget.insert("end", "Assistant: ", "assistant_label")

                # Store the response position for copy functionality
                response_start = chat_widget.index("end-1c")
                chat_widget.insert("end", ai_response, ("assistant_response", f"response_{timestamp}"))
                response_end = chat_widget.index("end-1c")

                # Add copy button after the response
                chat_widget.insert("end", "  ")

                import ttkbootstrap as ttk

                # Create a small frame to hold the button
                button_frame = tk.Frame(chat_widget, bg=chat_widget.cget('bg'))

                copy_btn = ttk.Button(
                    button_frame,
                    text="Copy",
                    bootstyle="secondary-link",
                    command=lambda r=ai_response: self._copy_to_clipboard(r)
                )
                copy_btn.pack(padx=2)

                # Add tooltip
                from ui.tooltip import ToolTip
                ToolTip(copy_btn, "Copy this response to clipboard")

                # Create window for button frame in text widget
                chat_widget.window_create("end-1c", window=button_frame)

                # Track for cleanup on chat clear
                self._chat_embedded_widgets.append(button_frame)
                chat_widget.insert("end", "\n")

                # Bind right-click to the response text
                chat_widget.tag_bind(f"response_{timestamp}", "<Button-3>",
                                   lambda e, r=ai_response: self._show_copy_menu(e, r))

                # Bind double-click to select the entire response
                chat_widget.tag_bind(f"response_{timestamp}", "<Double-Button-1>",
                                   lambda e: self._select_response(e, response_start, response_end))

                # Configure tags for styling
                chat_widget.tag_config("timestamp", foreground="gray", font=("Arial", 9))
                chat_widget.tag_config("user", foreground="#0066cc", font=("Arial", 11, "bold"))
                chat_widget.tag_config("assistant_label", foreground="#008800", font=("Arial", 11, "bold"))
                chat_widget.tag_config("assistant_response", foreground="#008800", font=("Arial", 11))
                chat_widget.tag_config("tool_header", foreground="#FF6B35", font=("Arial", 10, "bold"))
                chat_widget.tag_config("tool_name", foreground="#FF6B35", font=("Arial", 10))
                chat_widget.tag_config("tool_args", foreground="#999999", font=("Arial", 9))

                # Add hover effect for responses
                chat_widget.tag_bind(f"response_{timestamp}", "<Enter>",
                                   lambda e: chat_widget.config(cursor="hand2"))
                chat_widget.tag_bind(f"response_{timestamp}", "<Leave>",
                                   lambda e: chat_widget.config(cursor=""))

                # Scroll to bottom
                chat_widget.see("end")

                # Save to database if we have a current recording
                if hasattr(self.app, 'current_recording_id') and self.app.current_recording_id:
                    try:
                        full_chat = chat_widget.get("1.0", "end-1c")
                        if self.app.db.update_recording(self.app.current_recording_id, chat=full_chat):
                            logger.info(f"Updated recording {self.app.current_recording_id} with chat content")
                    except sqlite3.Error as e:
                        logger.error(f"Failed to save chat to database: {e}")

                # Update status
                self.app.status_manager.success("Chat response added")

            except (tk.TclError, AttributeError) as e:
                logger.error(f"Error appending to chat tab: {e}")
                self.app.status_manager.error("Failed to add chat response")

        # Execute on main thread
        self.app.after(0, append_chat)

    def _handle_chat_command(self, message: str) -> bool:
        """Handle special chat commands. Returns True if command was handled."""
        message_lower = message.lower().strip()

        if message_lower in ["clear chat history", "clear chat", "clear", "/clear"]:
            def clear_chat():
                try:
                    # Destroy embedded widgets (copy buttons) to prevent memory leak
                    for widget in self._chat_embedded_widgets:
                        try:
                            widget.destroy()
                        except tk.TclError:
                            pass
                    self._chat_embedded_widgets.clear()

                    # Clear the chat text widget
                    self.app.chat_text.delete("1.0", "end")
                    # Clear conversation history
                    self.clear_history()
                    # Update status
                    self.app.status_manager.success("Chat history cleared")
                except (tk.TclError, AttributeError) as e:
                    logger.error(f"Error clearing chat: {e}")
                    self.app.status_manager.error("Failed to clear chat")

            self.app.after(0, clear_chat)
            return True

        return False

    def _show_typing_indicator(self):
        """Show a typing indicator in the chat widget while processing."""
        def show():
            try:
                chat_widget = self.app.chat_text

                # Mark the position where we insert the indicator
                self._typing_indicator_mark = chat_widget.index("end-1c")

                # Insert initial typing indicator
                chat_widget.insert("end", "\n" + self._typing_frames[0], "typing_indicator")
                chat_widget.tag_config("typing_indicator", foreground="#888888", font=("Arial", 10, "italic"))

                # Scroll to bottom
                chat_widget.see("end")

                # Start animation
                self._animate_typing_indicator()

            except (tk.TclError, AttributeError) as e:
                logger.debug(f"Error showing typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, show)

    def _animate_typing_indicator(self):
        """Animate the typing indicator with dots."""
        def animate():
            try:
                if not self._typing_indicator_mark:
                    return

                chat_widget = self.app.chat_text

                # Delete old indicator text
                chat_widget.delete(self._typing_indicator_mark, "end-1c")

                # Cycle through frames
                self._typing_frame_index = (self._typing_frame_index + 1) % len(self._typing_frames)

                # Insert new frame
                chat_widget.insert(self._typing_indicator_mark, self._typing_frames[self._typing_frame_index], "typing_indicator")

                # Schedule next animation
                self._typing_animation_id = self.app.after(500, animate)

            except (tk.TclError, AttributeError) as e:
                logger.debug(f"Error animating typing indicator: {e}")

        animate()

    def _hide_typing_indicator(self):
        """Hide the typing indicator."""
        def hide():
            try:
                # Cancel animation
                if self._typing_animation_id:
                    try:
                        self.app.after_cancel(self._typing_animation_id)
                    except (tk.TclError, ValueError) as e:
                        logger.debug(f"Failed to cancel typing animation: {e}")
                    self._typing_animation_id = None

                # Remove indicator text if mark exists
                if self._typing_indicator_mark:
                    chat_widget = self.app.chat_text
                    chat_widget.delete(self._typing_indicator_mark, "end-1c")
                    self._typing_indicator_mark = None

                self._typing_frame_index = 0

            except (tk.TclError, AttributeError) as e:
                logger.debug(f"Error hiding typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, hide)

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            try:
                import pyperclip
                pyperclip.copy(text)
            except ImportError:
                self.app.clipboard_clear()
                self.app.clipboard_append(text)
                self.app.update()

            self.app.status_manager.success("Response copied to clipboard")
            logger.info("Assistant response copied to clipboard")
        except (tk.TclError, OSError) as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            self.app.status_manager.error("Failed to copy response")

    def _show_copy_menu(self, event, response_text: str):
        """Show context menu for copying response."""
        try:
            context_menu = tk.Menu(self.app, tearoff=0)
            context_menu.add_command(
                label="Copy Response",
                command=lambda: self._copy_to_clipboard(response_text)
            )
            context_menu.add_separator()
            context_menu.add_command(
                label="Select All",
                command=lambda: event.widget.tag_add(tk.SEL, "1.0", tk.END)
            )

            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

        except (tk.TclError, AttributeError) as e:
            logger.error(f"Error showing context menu: {e}")

    def _select_response(self, event, start_idx, end_idx):
        """Select an entire response when double-clicked."""
        try:
            event.widget.tag_remove(tk.SEL, "1.0", tk.END)
            event.widget.tag_add(tk.SEL, start_idx, end_idx)
            event.widget.focus_set()
        except (tk.TclError, AttributeError) as e:
            logger.error(f"Error selecting response: {e}")
