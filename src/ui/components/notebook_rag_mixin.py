"""
RAG-related mixin for NotebookTabs.

This mixin provides all RAG (Retrieval-Augmented Generation) related methods
for the NotebookTabs class, including document upload, library management,
knowledge graph visualization, search filters, and conversation export.
"""

from __future__ import annotations

import threading
import tkinter as tk
from typing import Any, Dict, List, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class NotebookRagMixin:
    """Mixin providing RAG-related methods for NotebookTabs.

    Expects the host class to provide:
        - self.parent: The parent window (WorkflowUI)
        - self.components: Dict of UI component references
        - self.rag_doc_count_label: Label widget for document count
        - self._rag_filters_visible: bool
        - self._rag_filters_panel: Optional filters panel
        - self._rag_health_indicators: Dict of health indicator widgets
    """

    def _clear_rag_history(self) -> None:
        """Clear the RAG conversation history."""
        try:
            # Clear the RAG processor history
            if hasattr(self.parent, 'rag_processor') and self.parent.rag_processor:
                self.parent.rag_processor.clear_history()

            # Clear the RAG text widget
            if 'rag_text' in self.components:
                rag_text = self.components['rag_text']
                rag_text.config(state=tk.NORMAL)
                rag_text.delete("1.0", tk.END)

                # Re-add welcome message
                rag_text.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                rag_text.insert("end", "This interface allows you to search your document database:\n")
                rag_text.insert("end", "\u2022 Query documents stored in your RAG database\n")
                rag_text.insert("end", "\u2022 Get relevant information from your knowledge base\n")
                rag_text.insert("end", "\u2022 Search through previously uploaded documents\n\n")
                rag_text.insert("end", "Type your question in the AI Assistant chat box below to search your documents!\n")
                rag_text.insert("end", "="*50 + "\n\n")

                # Configure initial styling
                rag_text.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                rag_text.tag_add("welcome", "1.0", "9.end")

                rag_text.config(state=tk.DISABLED)

            # Show success message
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.success("RAG history cleared")

            logger.info("RAG history cleared successfully")

        except tk.TclError as e:
            logger.error(f"Error clearing RAG history: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to clear RAG history")

    def _cancel_rag_query(self) -> None:
        """Cancel the current RAG query if one is in progress."""
        try:
            if hasattr(self.parent, 'rag_processor') and self.parent.rag_processor:
                if self.parent.rag_processor.cancel_current_query():
                    logger.info("RAG query cancellation requested")
                    if hasattr(self.parent, 'status_manager'):
                        self.parent.status_manager.info("Cancelling search...")
                    # Hide cancel button
                    self._hide_cancel_button()
                else:
                    logger.debug("No RAG query to cancel")
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Error cancelling RAG query: {e}")

    def show_cancel_button(self) -> None:
        """Show the cancel button when a RAG query starts."""
        try:
            if 'cancel_rag_button' in self.components:
                self.components['cancel_rag_button'].pack(side=tk.RIGHT, padx=(0, 5))
        except tk.TclError as e:
            logger.debug(f"Error showing cancel button: {e}")

    def _hide_cancel_button(self) -> None:
        """Hide the cancel button when a RAG query completes."""
        try:
            if 'cancel_rag_button' in self.components:
                self.components['cancel_rag_button'].pack_forget()
        except tk.TclError as e:
            logger.debug(f"Error hiding cancel button: {e}")

    def _show_rag_upload_dialog(self) -> None:
        """Show the RAG document upload dialog."""
        try:
            from ui.dialogs.rag_upload_dialog import RAGUploadDialog

            def on_upload(files: List[str], options: Dict[str, Any]) -> None:
                """Handle upload start."""
                self._process_rag_uploads(files, options)

            dialog = RAGUploadDialog(self.parent, on_upload=on_upload)
            dialog.wait_window()
            self._update_rag_document_count()

        except Exception as e:
            logger.error(f"Error showing RAG upload dialog: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open upload dialog: {e}")

    def _process_rag_uploads(self, files: List[str], options: Dict[str, Any]) -> None:
        """Process uploaded files in background thread.

        Args:
            files: List of file paths to upload
            options: Upload options (category, tags, enable_ocr, enable_graph)
        """
        import threading

        def upload_thread():
            try:
                from managers.rag_document_manager import get_rag_document_manager
                from ui.dialogs.rag_upload_dialog import RAGUploadProgressDialog

                manager = get_rag_document_manager()

                # Show progress dialog
                self.parent.after(0, lambda: self._show_upload_progress(files, options, manager))

            except Exception as e:
                logger.error(f"Error processing RAG uploads: {e}")
                error_msg = str(e)
                self.parent.after(0, lambda msg=error_msg: self._show_upload_error(msg))

        thread = threading.Thread(target=upload_thread, daemon=True)
        thread.start()

    def _show_upload_progress(self, files: List[str], options: Dict[str, Any], manager: Any) -> None:
        """Show upload progress dialog and process files.

        Args:
            files: List of file paths
            options: Upload options
            manager: RAGDocumentManager instance
        """
        from ui.dialogs.rag_upload_dialog import RAGUploadProgressDialog

        progress_dialog = RAGUploadProgressDialog(self.parent, len(files))

        def process_files():
            success_count = 0
            fail_count = 0

            for i, file_path in enumerate(files):
                if progress_dialog.cancelled:
                    break

                import os
                filename = os.path.basename(file_path)
                try:
                    if self.parent.winfo_exists():
                        self.parent.after(0, lambda f=filename, idx=i: progress_dialog.update_file_start(f, idx))
                except (tk.TclError, Exception):
                    pass

                try:
                    def progress_callback(progress):
                        try:
                            if self.parent.winfo_exists():
                                self.parent.after(0, lambda p=progress: progress_dialog.update_file_progress(p))
                        except (tk.TclError, Exception):
                            pass

                    manager.upload_document(
                        file_path=file_path,
                        category=options.get("category"),
                        tags=options.get("tags", []),
                        enable_ocr=options.get("enable_ocr", True),
                        enable_graph=options.get("enable_graph", True),
                        progress_callback=progress_callback,
                    )
                    success_count += 1
                    try:
                        if self.parent.winfo_exists():
                            self.parent.after(0, lambda: progress_dialog.update_file_complete(True))
                    except (tk.TclError, Exception):
                        pass

                except Exception as e:
                    logger.error(f"Failed to upload {filename}: {e}")
                    fail_count += 1
                    try:
                        if self.parent.winfo_exists():
                            self.parent.after(0, lambda: progress_dialog.update_file_complete(False))
                    except (tk.TclError, Exception):
                        pass

            try:
                if self.parent.winfo_exists():
                    self.parent.after(0, progress_dialog.complete)
            except (tk.TclError, Exception):
                pass
            try:
                if self.parent.winfo_exists():
                    self.parent.after(0, self._update_rag_document_count)
            except (tk.TclError, Exception):
                pass

            if success_count > 0 and hasattr(self.parent, 'status_manager'):
                try:
                    if self.parent.winfo_exists():
                        self.parent.after(0, lambda: self.parent.status_manager.success(
                            f"Uploaded {success_count} document(s)"
                        ))
                except (tk.TclError, Exception):
                    pass

        import threading
        thread = threading.Thread(target=process_files, daemon=True)
        thread.start()

    def _show_upload_error(self, error_msg: str) -> None:
        """Show upload error message."""
        from tkinter import messagebox
        messagebox.showerror("Upload Error", f"Failed to start upload:\n{error_msg}", parent=self.parent)

    def _show_rag_library_dialog(self) -> None:
        """Show the RAG document library dialog."""
        try:
            from ui.dialogs.rag_document_library_dialog import RAGDocumentLibraryDialog
            from managers.rag_document_manager import get_rag_document_manager

            manager = get_rag_document_manager()

            # Sync remote documents before loading the list
            try:
                synced = manager.sync_from_remote()
                if synced > 0:
                    logger.info(f"Synced {synced} remote document(s) into local library")
            except Exception as e:
                logger.debug(f"Remote sync before library open failed: {e}")

            documents = manager.get_documents()

            def on_delete(doc_id: str) -> bool:
                return manager.delete_document(doc_id)

            def on_refresh():
                return manager.get_documents()

            def on_reprocess(doc_id: str):
                # Reprocess document - would need implementation
                logger.info(f"Reprocess requested for document {doc_id}")

            dialog = RAGDocumentLibraryDialog(
                self.parent,
                documents=documents,
                on_delete=on_delete,
                on_refresh=on_refresh,
                on_reprocess=on_reprocess,
            )
            dialog.wait_window()
            self._update_rag_document_count()

        except Exception as e:
            logger.error(f"Error showing RAG library dialog: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open document library: {e}")

    def _show_knowledge_graph_dialog(self) -> None:
        """Show the knowledge graph visualization dialog."""
        try:
            from ui.dialogs.knowledge_graph_dialog import KnowledgeGraphDialog
            from rag.graphiti_client import get_graphiti_client

            graphiti = get_graphiti_client()
            dialog = KnowledgeGraphDialog(self.parent, graphiti_client=graphiti)
            dialog.wait_window()

        except Exception as e:
            logger.error(f"Error showing knowledge graph dialog: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open knowledge graph: {e}")

    def _update_rag_document_count(self) -> None:
        """Update the RAG document count label."""
        try:
            if not hasattr(self, 'rag_doc_count_label'):
                return

            from managers.rag_document_manager import get_rag_document_manager
            manager = get_rag_document_manager()
            count = manager.get_document_count()

            if count == 0:
                text = "No documents"
            elif count == 1:
                text = "1 document"
            else:
                text = f"{count} documents"

            self.rag_doc_count_label.config(text=text)

        except Exception as e:
            logger.debug(f"Could not update RAG document count: {e}")
            if hasattr(self, 'rag_doc_count_label'):
                self.rag_doc_count_label.config(text="")

    def _refresh_rag_health_indicators(self) -> None:
        """Refresh the RAG component health indicator colors.

        Runs the health check in a background thread to avoid blocking the UI.
        Colors: green = healthy, red = circuit open, gray = unknown/checking.
        """
        if not hasattr(self, '_rag_health_indicators'):
            return

        def _check_health():
            try:
                from rag.rag_resilience import (
                    is_neon_available,
                    is_neo4j_available,
                    is_openai_embedding_available,
                )
                neon_ok = is_neon_available()
                statuses = {
                    "vector": neon_ok and is_openai_embedding_available(),
                    "bm25": neon_ok,
                    "graph": is_neo4j_available(),
                }
            except Exception:
                statuses = {"vector": None, "bm25": None, "graph": None}

            # Schedule UI update on main thread
            try:
                parent = self.parent.parent if hasattr(self.parent, 'parent') else self.parent
                if hasattr(parent, 'after'):
                    parent.after(0, lambda: self._apply_health_colors(statuses))
            except Exception:
                pass

        thread = threading.Thread(
            target=_check_health, daemon=True, name="rag_health_check"
        )
        thread.start()

    def _apply_health_colors(self, statuses: dict) -> None:
        """Apply health status colors to the indicators.

        Args:
            statuses: Dict mapping component name to True/False/None
        """
        if not hasattr(self, '_rag_health_indicators'):
            return

        color_map = {True: "#28a745", False: "#dc3545", None: "gray"}

        for comp_name, indicator in self._rag_health_indicators.items():
            try:
                if indicator.winfo_exists():
                    status = statuses.get(comp_name)
                    indicator.config(foreground=color_map.get(status, "gray"))
            except Exception:
                pass

    def _export_rag_conversation(self, format: str) -> None:
        """Export RAG conversation history to specified format.

        Args:
            format: Export format ('pdf', 'docx', 'md', 'json')
        """
        try:
            from tkinter import filedialog
            from datetime import datetime
            from pathlib import Path

            # Get RAG processor and conversation history
            if not hasattr(self.parent, 'rag_processor') or not self.parent.rag_processor:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No RAG conversation to export")
                return

            # Get conversation data from processor
            conversation_data = self.parent.rag_processor.get_conversation_export_data()
            if not conversation_data or not conversation_data.get('exchanges'):
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No RAG conversation to export")
                return

            # File extension mapping
            ext_map = {'pdf': '.pdf', 'docx': '.docx', 'md': '.md', 'json': '.json'}
            ext = ext_map.get(format, '.json')

            # Default filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = f"rag_conversation_{timestamp}{ext}"

            # File type filter
            filetypes = {
                'pdf': [("PDF Files", "*.pdf")],
                'docx': [("Word Documents", "*.docx")],
                'md': [("Markdown Files", "*.md")],
                'json': [("JSON Files", "*.json")],
            }

            # Ask for save location
            filepath = filedialog.asksaveasfilename(
                parent=self.parent,
                defaultextension=ext,
                filetypes=filetypes.get(format, [("All Files", "*.*")]),
                initialfile=default_name,
                title=f"Export RAG Conversation as {format.upper()}"
            )

            if not filepath:
                return  # User cancelled

            # Export using RAG exporter
            from exporters.rag_exporter import get_rag_exporter
            exporter = get_rag_exporter()

            success = exporter.export(conversation_data, Path(filepath))

            if success:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.success(f"Exported to {Path(filepath).name}")
            else:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.error(f"Export failed: {exporter.last_error}")

        except Exception as e:
            logger.error(f"Error exporting RAG conversation: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Export failed: {str(e)}")

    def _toggle_rag_filters(self) -> None:
        """Toggle visibility of the RAG filters panel."""
        try:
            self._rag_filters_visible = not getattr(self, '_rag_filters_visible', False)

            filters_frame = self.components.get('rag_filters_frame')
            if not filters_frame:
                return

            if self._rag_filters_visible:
                # Lazy initialize filters panel
                if self._rag_filters_panel is None:
                    try:
                        from ui.components.search_filters import CompactFiltersBar
                        self._rag_filters_panel = CompactFiltersBar(
                            filters_frame,
                            on_filters_changed=self._on_rag_filters_changed
                        )
                    except Exception as e:
                        logger.error(f"Could not create filters panel: {e}")
                        return

                # Show filters
                filters_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2, before=self.components.get('rag_text'))
                if self._rag_filters_panel:
                    self._rag_filters_panel.show()

                # Update button style
                if 'rag_filters_button' in self.components:
                    self.components['rag_filters_button'].config(bootstyle="secondary")
            else:
                # Hide filters
                if self._rag_filters_panel:
                    self._rag_filters_panel.hide()
                filters_frame.pack_forget()

                # Reset button style
                if 'rag_filters_button' in self.components:
                    self.components['rag_filters_button'].config(bootstyle="secondary-outline")

        except Exception as e:
            logger.error(f"Error toggling RAG filters: {e}")

    def _on_rag_filters_changed(self, filters: Any) -> None:
        """Handle RAG filter changes.

        Args:
            filters: SearchFilters object with current settings
        """
        try:
            # Store current filters for use in queries
            self._current_rag_filters = filters

            # Update status to show active filters
            if hasattr(self.parent, 'status_manager') and filters.has_filters():
                filter_summary = []
                if filters.document_types:
                    filter_summary.append(f"types:{','.join(filters.document_types)}")
                if filters.date_start:
                    filter_summary.append("date filter active")
                if filters.entity_types:
                    filter_summary.append(f"entities:{','.join(filters.entity_types)}")
                if filters.min_score > 0:
                    filter_summary.append(f"score>{filters.min_score:.0%}")

                self.parent.status_manager.info(f"Filters: {', '.join(filter_summary)}")

        except Exception as e:
            logger.debug(f"Error handling filter change: {e}")

    def _show_search_syntax_help(self) -> None:
        """Show help dialog for advanced search syntax."""
        try:
            from rag.search_syntax_parser import get_search_syntax_parser

            parser = get_search_syntax_parser()
            help_text = parser.format_help()

            # Create help dialog
            dialog = tk.Toplevel(self.parent)
            dialog.title("Advanced Search Syntax")
            dialog.geometry("550x500")
            dialog.transient(self.parent)

            # Create text widget with scrollbar
            import ttkbootstrap as ttk
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(
                frame,
                wrap=tk.WORD,
                yscrollcommand=scrollbar.set,
                font=("Consolas", 10)
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=text_widget.yview)

            # Insert help text
            text_widget.insert('1.0', help_text)
            text_widget.config(state='disabled')

            # Configure tags for styling
            text_widget.tag_configure("header", font=("Consolas", 11, "bold"))

            # Add close button
            close_btn = ttk.Button(
                dialog,
                text="Close",
                command=dialog.destroy,
                bootstyle="secondary"
            )
            close_btn.pack(pady=10)

            # Center the dialog
            dialog.update_idletasks()
            x = self.parent.winfo_x() + (self.parent.winfo_width() - dialog.winfo_width()) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        except Exception as e:
            logger.error(f"Error showing syntax help: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to show syntax help")

    def get_rag_source_highlighter(self) -> Optional[Any]:
        """Get the RAG source highlighter instance.

        Returns:
            SourceHighlighter instance or None
        """
        return getattr(self, '_rag_source_highlighter', None)

    def get_rag_source_legend(self) -> Optional[Any]:
        """Get the RAG source legend instance.

        Returns:
            SourceLegend instance or None
        """
        return getattr(self, '_rag_source_legend', None)

    def get_current_rag_filters(self) -> Optional[Any]:
        """Get the current RAG filter settings.

        Returns:
            SearchFilters object or None
        """
        return getattr(self, '_current_rag_filters', None)
