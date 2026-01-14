"""
Record Tab Component for Medical Assistant
Handles the recording workflow UI elements
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, LEFT, RIGHT
import logging
from datetime import datetime
from typing import Dict, Callable, Optional
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from ui.ui_constants import Icons
from settings.settings import SETTINGS, save_settings


class RecordTab:
    """Manages the Record workflow tab UI components.

    Note: Recording controls (buttons, timer, waveform) are now in RecordingHeader.
    This tab now primarily displays the Advanced Analysis Results.
    """

    def __init__(self, parent_ui):
        """Initialize the RecordTab component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
    def create_record_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Record workflow tab (legacy - for backwards compatibility).

        Args:
            command_map: Dictionary of commands

        Returns:
            ttk.Frame: The record tab frame
        """
        # For backwards compatibility, delegate to create_analysis_panel
        return self.create_analysis_panel(self.parent, command_map)

    def create_analysis_panel(self, parent, command_map: Optional[Dict[str, Callable]] = None, show_collapse_button: bool = True) -> ttk.Frame:
        """Create the Advanced Analysis Results panel.

        This is the main panel that shows analysis results during recording.
        It takes full width in the shared panel area.

        Args:
            parent: Parent widget for the panel
            command_map: Optional dictionary of commands
            show_collapse_button: Whether to show the individual collapse button

        Returns:
            ttk.Frame: The analysis panel frame
        """
        # Store command map for later use
        if command_map:
            self._command_map = command_map

        self._show_collapse_button = show_collapse_button
        analysis_frame = ttk.Frame(parent)

        # Create placeholder components for backwards compatibility
        self._create_placeholder_components()

        # Main content frame with padding
        content_frame = ttk.Frame(analysis_frame)
        content_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # Get initial collapse state from settings - always expanded when unified button is used
        self._analysis_results_collapsed = SETTINGS.get("advanced_analysis_collapsed", False) if show_collapse_button else False

        # Create header frame with title and optional collapse button
        if show_collapse_button:
            header_frame = ttk.Frame(content_frame)
            header_frame.pack(fill=X, pady=(0, 2))

            # Collapse button on the left
            initial_icon = Icons.COLLAPSE if self._analysis_results_collapsed else Icons.EXPAND
            self._analysis_collapse_btn = ttk.Button(
                header_frame,
                text=initial_icon,
                width=3,
                bootstyle="secondary-outline",
                command=self._toggle_analysis_results_panel
            )
            self._analysis_collapse_btn.pack(side=LEFT, padx=(0, 5))
            self._analysis_collapse_tooltip = ToolTip(
                self._analysis_collapse_btn,
                "Expand Analysis Results" if self._analysis_results_collapsed else "Collapse Analysis Results"
            )
            self.components['advanced_analysis_collapse_btn'] = self._analysis_collapse_btn

            # Title label
            title_label = ttk.Label(header_frame, text="Advanced Analysis Results", font=("", 10, "bold"))
            title_label.pack(side=LEFT)

        # Create collapsible content frame (using regular frame instead of Labelframe)
        self._analysis_content_frame = ttk.Frame(content_frame)
        self.components['advanced_analysis_content'] = self._analysis_content_frame

        # Only pack if not collapsed (or always if using unified button)
        if not self._analysis_results_collapsed or not show_collapse_button:
            self._analysis_content_frame.pack(fill=BOTH, expand=True)

        # Create text area inside the content frame
        text_frame = ttk.Frame(self._analysis_content_frame, padding=10)
        text_frame.pack(fill=BOTH, expand=True)

        # Create controls frame with countdown and buttons
        controls_frame = ttk.Frame(text_frame)
        controls_frame.pack(fill=X, pady=(0, 5))

        # Countdown label on the left
        self.countdown_label = ttk.Label(controls_frame, text="", width=14, anchor="w")
        self.countdown_label.pack(side=LEFT)
        self.components['countdown_label'] = self.countdown_label

        # Button row on the right
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(side=RIGHT)

        copy_btn = ttk.Button(
            button_frame,
            text="Copy",
            command=self._copy_analysis,
            bootstyle="secondary-outline",
            width=6
        )
        copy_btn.pack(side=LEFT, padx=2)
        ToolTip(copy_btn, "Copy analysis to clipboard")
        self.components['copy_analysis_button'] = copy_btn

        soap_btn = ttk.Button(
            button_frame,
            text="→ SOAP",
            command=self._add_analysis_to_soap,
            bootstyle="info-outline",
            width=7
        )
        soap_btn.pack(side=LEFT, padx=2)
        ToolTip(soap_btn, "Add analysis to SOAP note")
        self.components['soap_analysis_button'] = soap_btn

        clear_btn = ttk.Button(
            button_frame,
            text="Clear",
            command=self._clear_analysis,
            bootstyle="secondary-outline",
            width=6
        )
        clear_btn.pack(side=LEFT, padx=2)
        ToolTip(clear_btn, "Clear analysis results")
        self.components['clear_analysis_button'] = clear_btn

        # Create text widget with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=BOTH, expand=True)

        text_scroll = ttk.Scrollbar(text_container)
        text_scroll.pack(side=RIGHT, fill=Y)

        self.components['record_notes_text'] = tk.Text(
            text_container,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set
        )
        self.components['record_notes_text'].pack(fill=BOTH, expand=True)
        text_scroll.config(command=self.components['record_notes_text'].yview)

        # Add empty state hint
        self._show_empty_state_hint()

        return analysis_frame

    def _create_placeholder_components(self):
        """Create placeholder component references for backwards compatibility.

        The actual recording controls are now in the header. This method sets up
        references so that code expecting record tab components still works.
        """
        # These will be redirected to header controls after header is created
        # For now, set to None - they'll be updated by _link_to_header_controls
        self.components['main_record_button'] = None
        self.components['pause_button'] = None
        self.components['cancel_button'] = None
        self.components['timer_label'] = None

    def link_to_header_controls(self):
        """Link component references to header controls.

        Called after the recording header is created to redirect
        component references to the header controls.
        """
        # Get header components
        header_record = self.components.get('header_record_button')
        header_pause = self.components.get('header_pause_button')
        header_cancel = self.components.get('header_cancel_button')
        header_timer = self.components.get('header_timer_label')

        # Update main component references to point to header controls
        if header_record:
            self.components['main_record_button'] = header_record
        if header_pause:
            self.components['pause_button'] = header_pause
        if header_cancel:
            self.components['cancel_button'] = header_cancel
        if header_timer:
            self.components['timer_label'] = header_timer

        # Link advanced analysis vars from header
        if hasattr(self.parent_ui, 'recording_header') and self.parent_ui.recording_header:
            header = self.parent_ui.recording_header
            if hasattr(header, 'advanced_analysis_var'):
                self.parent_ui.advanced_analysis_var = header.advanced_analysis_var
            if hasattr(header, 'analysis_interval_var'):
                self.parent_ui.analysis_interval_var = header.analysis_interval_var

    def _initialize_recording_ui_state(self):
        """Initialize the recording UI to its default state.

        Most controls are now in the header, so this is simplified.
        """
        pass  # Recording controls are now in the header
    
    def set_recording_state(self, recording: bool, paused: bool = False):
        """Update UI elements based on recording state.

        Recording controls are now in the header. This method handles
        any Record tab-specific state changes.

        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        logging.info(f"RecordTab.set_recording_state called: recording={recording}, paused={paused}")

        if recording and not paused:
            # Clear the analysis display when starting a new recording
            text_widget = self.components.get('record_notes_text')
            if text_widget:
                current = text_widget.get("1.0", "end-1c")
                # Only clear if there's actual content (not just the hint)
                if current.strip() and "will appear here" not in current:
                    # Keep existing analysis - don't clear during recording
                    pass
        elif not recording:
            # Recording stopped - optionally clear for next session
            # (Analysis results are kept until explicitly cleared)
            pass
    
    # Note: Timer and animation methods removed - now handled by RecordingHeader

    # ==================== Advanced Analysis Methods ====================

    def _show_empty_state_hint(self):
        """Show the empty state hint in the analysis text area."""
        text_widget = self.components.get('record_notes_text')
        if text_widget:
            text_widget.delete("1.0", tk.END)
            hint_text = (
                "Advanced Analysis results will appear here during recording.\n\n"
                "To enable:\n"
                "1. Check 'Advanced Analysis' in the header above\n"
                "2. Select the analysis interval (1, 2, or 5 minutes)\n"
                "3. Click 'Start Recording'\n\n"
                "Real-time differential diagnosis suggestions will appear here\n"
                "with timestamps as you record."
            )
            text_widget.insert("1.0", hint_text)
            text_widget.config(foreground="gray")

    def _copy_analysis(self):
        """Copy analysis results to clipboard."""
        text_widget = self.components.get('record_notes_text')
        if not text_widget:
            return

        text = text_widget.get("1.0", "end-1c").strip()

        # Don't copy the empty state hint
        if not text or "will appear here" in text:
            self._show_feedback("Nothing to copy")
            return

        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(text)
            self._show_feedback("Copied to clipboard")
        except Exception as e:
            logging.error(f"Error copying analysis: {e}")
            self._show_feedback("Copy failed")

    def _add_analysis_to_soap(self):
        """Add analysis results to SOAP note."""
        text_widget = self.components.get('record_notes_text')
        if not text_widget:
            return

        text = text_widget.get("1.0", "end-1c").strip()

        # Don't add the empty state hint
        if not text or "will appear here" in text:
            self._show_feedback("No analysis to add")
            return

        try:
            # Find the SOAP text widget in parent
            soap_text = None
            if hasattr(self.parent_ui, 'parent') and hasattr(self.parent_ui.parent, 'ui'):
                ui = self.parent_ui.parent.ui
                if hasattr(ui, 'components') and 'soap_text' in ui.components:
                    soap_text = ui.components['soap_text']

            if soap_text:
                # Append to SOAP note with separator
                soap_text.insert(tk.END, f"\n\n{'─' * 40}\nAdvanced Analysis:\n{'─' * 40}\n{text}")
                soap_text.see(tk.END)
                self._show_feedback("Added to SOAP note")
            else:
                self._show_feedback("SOAP note not available")
        except Exception as e:
            logging.error(f"Error adding to SOAP: {e}")
            self._show_feedback("Failed to add")

    def _clear_analysis(self):
        """Clear the analysis text and show empty state."""
        self._show_empty_state_hint()
        self.update_countdown(0, clear=True)
        self._show_feedback("Cleared")

    def _toggle_analysis_results_panel(self) -> None:
        """Toggle collapse/expand state of the Advanced Analysis Results panel.

        When collapsed, the content is hidden and only the header remains visible.
        """
        # Don't toggle if using unified collapse button (no individual button)
        if not getattr(self, '_show_collapse_button', True):
            return

        self._analysis_results_collapsed = not self._analysis_results_collapsed
        logging.info(f"[PANEL DEBUG] Analysis panel toggled. New state: collapsed={self._analysis_results_collapsed}")

        # Save state to settings
        SETTINGS["advanced_analysis_collapsed"] = self._analysis_results_collapsed
        save_settings(SETTINGS)

        if self._analysis_results_collapsed:
            # Collapse: hide the content
            self._analysis_content_frame.pack_forget()
            if hasattr(self, '_analysis_collapse_btn') and self._analysis_collapse_btn:
                self._analysis_collapse_btn.config(text=Icons.COLLAPSE)
            if hasattr(self, '_analysis_collapse_tooltip') and self._analysis_collapse_tooltip:
                self._analysis_collapse_tooltip.text = "Expand Analysis Results"
            logging.info("[PANEL DEBUG] Analysis content frame hidden")
        else:
            # Expand: show the content
            self._analysis_content_frame.pack(fill=BOTH, expand=True)
            if hasattr(self, '_analysis_collapse_btn') and self._analysis_collapse_btn:
                self._analysis_collapse_btn.config(text=Icons.EXPAND)
            if hasattr(self, '_analysis_collapse_tooltip') and self._analysis_collapse_tooltip:
                self._analysis_collapse_tooltip.text = "Collapse Analysis Results"
            logging.info("[PANEL DEBUG] Analysis content frame shown")

        # Adjust the content paned sash to redistribute space
        self._adjust_content_paned_sash()

    def _adjust_content_paned_sash(self):
        """Adjust the content_paned sash position based on collapse states.

        Sizing requirements:
        - Both expanded: SOAP 60%, bottom 40%
        - Only Chat expanded: SOAP 90%, bottom 10%
        - Only Analysis expanded: SOAP 70%, bottom 30%
        - Both collapsed: SOAP max, bottom headers only (~50px)
        """
        logging.info("[PANEL DEBUG] _adjust_content_paned_sash called from record_tab")
        try:
            # Get the content_paned from UI components
            content_paned = self.components.get('content_paned')
            logging.info(f"[PANEL DEBUG] content_paned from components: {content_paned}")
            logging.info(f"[PANEL DEBUG] Available components keys: {list(self.components.keys())}")

            if not content_paned:
                logging.warning("[PANEL DEBUG] content_paned not found in components!")
                return

            # Check if chat is collapsed
            chat_collapsed = SETTINGS.get("chat_interface", {}).get("collapsed", False)
            logging.info(f"[PANEL DEBUG] chat_collapsed={chat_collapsed}, analysis_collapsed={self._analysis_results_collapsed}")

            # Get the total height of the content_paned
            content_paned.update_idletasks()
            total_height = content_paned.winfo_height()
            current_sash = content_paned.sashpos(0)
            logging.info(f"[PANEL DEBUG] total_height={total_height}, current_sash_pos={current_sash}")

            if total_height <= 1:
                logging.info("[PANEL DEBUG] total_height <= 1, skipping (not yet rendered)")
                return

            # Height for collapsed headers only
            HEADER_ONLY_HEIGHT = 50

            # Calculate sash position based on collapse states (percentage-based)
            # With horizontal layout, both panels are side by side in bottom section
            if self._analysis_results_collapsed and chat_collapsed:
                # Both collapsed - just headers visible (horizontal row)
                new_sash_pos = total_height - HEADER_ONLY_HEIGHT
                reason = "both collapsed (headers only)"
            elif self._analysis_results_collapsed or chat_collapsed:
                # One expanded - give moderate space for the expanded panel
                new_sash_pos = int(total_height * 0.75)
                reason = "one expanded (75/25)"
            else:
                # Both expanded - SOAP 60%, bottom 40%
                new_sash_pos = int(total_height * 0.60)
                reason = "both expanded (60/40)"

            logging.info(f"[PANEL DEBUG] Calculated new_sash_pos={new_sash_pos} ({reason})")

            # Get the bottom_section to configure its minimum size
            bottom_section = self.components.get('bottom_section')
            if bottom_section:
                # Allow the bottom section to shrink to a small size
                try:
                    panes = content_paned.panes()
                    logging.info(f"[PANEL DEBUG] Panes in content_paned: {panes}")
                    if len(panes) >= 2:
                        # Configure the second pane (bottom_section) to have a small minimum size
                        # Use 'pane' method for ttk.Panedwindow (not 'paneconfig')
                        min_height = HEADER_ONLY_HEIGHT if (self._analysis_results_collapsed and chat_collapsed) else 100
                        content_paned.pane(panes[1], weight=0)  # weight=0 prevents auto-resize
                        logging.info(f"[PANEL DEBUG] Set weight=0 for bottom pane")
                except Exception as e:
                    logging.error(f"[PANEL DEBUG] Error configuring pane: {e}")

            # Set the sash position (sash index 0 is between first two panes)
            content_paned.sashpos(0, new_sash_pos)

            # Force geometry update
            content_paned.update_idletasks()

            # Verify the change
            actual_sash = content_paned.sashpos(0)
            logging.info(f"[PANEL DEBUG] After setting: requested={new_sash_pos}, actual={actual_sash}")

        except Exception as e:
            logging.error(f"[PANEL DEBUG] Exception in _adjust_content_paned_sash: {e}", exc_info=True)

    def _show_feedback(self, message: str):
        """Show brief feedback in the countdown label."""
        if hasattr(self, 'countdown_label'):
            original_text = self.countdown_label.cget('text')
            self.countdown_label.config(text=message)
            # Restore after 2 seconds
            self.parent.after(2000, lambda: self.countdown_label.config(text=original_text))

    def update_countdown(self, seconds: int, clear: bool = False):
        """Update the countdown display.

        Args:
            seconds: Seconds remaining until next analysis
            clear: If True, clear the countdown display
        """
        if not hasattr(self, 'countdown_label'):
            return

        if clear:
            self.countdown_label.config(text="")
        elif seconds <= 0:
            self.countdown_label.config(text="Analyzing...")
        else:
            mins, secs = divmod(seconds, 60)
            self.countdown_label.config(text=f"Next: {mins}:{secs:02d}")

    def update_analysis_display(self, text: str):
        """Update analysis display with accumulated results.

        Args:
            text: New analysis text to append
        """
        text_widget = self.components.get('record_notes_text')
        if not text_widget:
            return

        try:
            # Get current content
            current = text_widget.get("1.0", "end-1c")

            # Clear empty state hint if present
            if "will appear here" in current:
                text_widget.delete("1.0", tk.END)
                text_widget.config(foreground="")  # Reset to default color
                current = ""

            # Add separator if not first entry
            if current.strip():
                text_widget.insert(tk.END, "\n\n" + "─" * 50 + "\n\n")

            # Add timestamped entry
            timestamp = datetime.now().strftime("%H:%M:%S")
            text_widget.insert(tk.END, f"[{timestamp}]\n{text}")
            text_widget.see(tk.END)

        except Exception as e:
            logging.error(f"Error updating analysis display: {e}")

    def get_analysis_interval_seconds(self) -> int:
        """Get the current analysis interval in seconds.

        Returns:
            Interval in seconds (60, 120, or 300)
        """
        try:
            # Get interval from parent_ui (set from header)
            if hasattr(self.parent_ui, 'analysis_interval_var') and self.parent_ui.analysis_interval_var:
                interval_str = self.parent_ui.analysis_interval_var.get()
            elif hasattr(self.parent_ui, 'recording_header') and self.parent_ui.recording_header:
                interval_str = self.parent_ui.recording_header.analysis_interval_var.get()
            else:
                return 120  # Default to 2 minutes

            minutes = int(interval_str.split()[0])
            return minutes * 60
        except (ValueError, IndexError, AttributeError):
            return 120  # Default to 2 minutes