"""
RAG & Guidelines tab mixin for UnifiedSettingsDialog.

Provides the _create_rag_guidelines_tab and _test_pg_connection methods.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RagGuidelinesTabMixin:
    """Mixin providing the RAG & Guidelines tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.widgets: Dict[str, Dict]
        - self.dialog: tk.Toplevel
        - self.parent: Parent window
    """

    def _create_rag_guidelines_tab(self):
        """Create RAG & Guidelines tab for database connection settings."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_RAG_GUIDELINES)

        # Create scrollable canvas
        canvas = tk.Canvas(tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)

        self.widgets['rag_guidelines'] = {}
        row = 0

        # --- RAG Database Settings ---
        ttk.Label(scrollable_frame, text="RAG Database Settings",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        # Neon Database URL
        neon_label = ttk.Label(scrollable_frame, text="Neon Database URL:")
        neon_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(neon_label, "PostgreSQL connection string for Neon pgvector RAG database")
        neon_url = os.environ.get("NEON_DATABASE_URL", "") or settings_manager.get("neon_database_url", "")
        neon_var = tk.StringVar(value=neon_url)
        self.widgets['rag_guidelines']['neon_database_url'] = neon_var
        neon_entry = ttk.Entry(scrollable_frame, textvariable=neon_var, width=50, show="\u2022")
        neon_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        ToolTip(neon_entry, "postgresql://user:pass@host/dbname (Neon pgvector)")

        # Toggle visibility + Test Connection
        btn_frame_neon = ttk.Frame(scrollable_frame)
        btn_frame_neon.grid(row=row, column=2, padx=5, pady=10)

        def toggle_neon(e=neon_entry):
            e['show'] = '' if e['show'] else '\u2022'
        ttk.Button(btn_frame_neon, text="\U0001f441", width=3, command=toggle_neon).pack(side="left", padx=(0, 2))
        ToolTip(btn_frame_neon.winfo_children()[0], "Show/hide URL")

        ttk.Button(btn_frame_neon, text="Test", width=6,
                  command=lambda: self._test_pg_connection(neon_var.get(), "RAG Database")).pack(side="left")
        ToolTip(btn_frame_neon.winfo_children()[1], "Test PostgreSQL connection")
        row += 1

        # --- Knowledge Graph ---
        ttk.Label(scrollable_frame, text="Knowledge Graph",
                 font=("Segoe UI", 11, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(15, 10))
        row += 1

        neo4j_uri = os.environ.get("NEO4J_URI", "") or settings_manager.get("neo4j_uri", "")
        neo4j_user = os.environ.get("NEO4J_USER", "") or settings_manager.get("neo4j_user", "")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "") or settings_manager.get("neo4j_password", "")

        # Neo4j URI
        uri_label = ttk.Label(scrollable_frame, text="Neo4j URI:")
        uri_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(uri_label, "Neo4j connection URI (e.g., bolt://localhost:7687)")
        uri_var = tk.StringVar(value=neo4j_uri)
        self.widgets['rag_guidelines']['neo4j_uri'] = uri_var
        ttk.Entry(scrollable_frame, textvariable=uri_var, width=50).grid(
            row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        row += 1

        # Neo4j User
        user_label = ttk.Label(scrollable_frame, text="Neo4j User:")
        user_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(user_label, "Neo4j username")
        user_var = tk.StringVar(value=neo4j_user)
        self.widgets['rag_guidelines']['neo4j_user'] = user_var
        ttk.Entry(scrollable_frame, textvariable=user_var, width=50).grid(
            row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        row += 1

        # Neo4j Password
        pw_label = ttk.Label(scrollable_frame, text="Neo4j Password:")
        pw_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(pw_label, "Neo4j password")
        pw_var = tk.StringVar(value=neo4j_password)
        self.widgets['rag_guidelines']['neo4j_password'] = pw_var
        pw_entry = ttk.Entry(scrollable_frame, textvariable=pw_var, width=50, show="\u2022")
        pw_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)

        def toggle_neo4j_pw(e=pw_entry):
            e['show'] = '' if e['show'] else '\u2022'
        ttk.Button(scrollable_frame, text="\U0001f441", width=3, command=toggle_neo4j_pw).grid(
            row=row, column=2, padx=5, pady=10)
        row += 1

        # --- Separator ---
        ttk.Separator(scrollable_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=20)
        row += 1

        # --- Clinical Guidelines Database ---
        ttk.Label(scrollable_frame, text="Clinical Guidelines Database",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        guidelines_settings = settings_manager.get("clinical_guidelines", {})

        # Guidelines Database URL
        gl_db_label = ttk.Label(scrollable_frame, text="Guidelines Database URL:")
        gl_db_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(gl_db_label, "PostgreSQL connection string for clinical guidelines database")
        gl_db_url = os.environ.get("CLINICAL_GUIDELINES_DATABASE_URL", "") or guidelines_settings.get("database_url", "")
        gl_db_var = tk.StringVar(value=gl_db_url)
        self.widgets['rag_guidelines']['guidelines_database_url'] = gl_db_var
        gl_db_entry = ttk.Entry(scrollable_frame, textvariable=gl_db_var, width=50, show="\u2022")
        gl_db_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        ToolTip(gl_db_entry, "postgresql://user:pass@host/dbname (guidelines)")

        btn_frame_gl = ttk.Frame(scrollable_frame)
        btn_frame_gl.grid(row=row, column=2, padx=5, pady=10)

        def toggle_gl_db(e=gl_db_entry):
            e['show'] = '' if e['show'] else '\u2022'
        ttk.Button(btn_frame_gl, text="\U0001f441", width=3, command=toggle_gl_db).pack(side="left", padx=(0, 2))
        ToolTip(btn_frame_gl.winfo_children()[0], "Show/hide URL")

        ttk.Button(btn_frame_gl, text="Test", width=6,
                  command=lambda: self._test_pg_connection(gl_db_var.get(), "Guidelines Database")).pack(side="left")
        ToolTip(btn_frame_gl.winfo_children()[1], "Test PostgreSQL connection")
        row += 1

        # --- Guidelines Knowledge Graph ---
        ttk.Label(scrollable_frame, text="Guidelines Knowledge Graph",
                 font=("Segoe UI", 11, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(15, 10))
        row += 1

        gl_neo4j_uri = os.environ.get("CLINICAL_GUIDELINES_NEO4J_URI", "") or guidelines_settings.get("neo4j_uri", "")
        gl_neo4j_user = os.environ.get("CLINICAL_GUIDELINES_NEO4J_USER", "") or guidelines_settings.get("neo4j_user", "")
        gl_neo4j_password = os.environ.get("CLINICAL_GUIDELINES_NEO4J_PASSWORD", "") or guidelines_settings.get("neo4j_password", "")

        # Guidelines Neo4j URI
        gl_uri_label = ttk.Label(scrollable_frame, text="Guidelines Neo4j URI:")
        gl_uri_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(gl_uri_label, "Neo4j URI for clinical guidelines knowledge graph")
        gl_uri_var = tk.StringVar(value=gl_neo4j_uri)
        self.widgets['rag_guidelines']['guidelines_neo4j_uri'] = gl_uri_var
        ttk.Entry(scrollable_frame, textvariable=gl_uri_var, width=50).grid(
            row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        row += 1

        # Guidelines Neo4j User
        gl_user_label = ttk.Label(scrollable_frame, text="Guidelines Neo4j User:")
        gl_user_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(gl_user_label, "Neo4j username for guidelines knowledge graph")
        gl_user_var = tk.StringVar(value=gl_neo4j_user)
        self.widgets['rag_guidelines']['guidelines_neo4j_user'] = gl_user_var
        ttk.Entry(scrollable_frame, textvariable=gl_user_var, width=50).grid(
            row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        row += 1

        # Guidelines Neo4j Password
        gl_pw_label = ttk.Label(scrollable_frame, text="Guidelines Neo4j Password:")
        gl_pw_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(gl_pw_label, "Neo4j password for guidelines knowledge graph")
        gl_pw_var = tk.StringVar(value=gl_neo4j_password)
        self.widgets['rag_guidelines']['guidelines_neo4j_password'] = gl_pw_var
        gl_pw_entry = ttk.Entry(scrollable_frame, textvariable=gl_pw_var, width=50, show="\u2022")
        gl_pw_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)

        def toggle_gl_neo4j_pw(e=gl_pw_entry):
            e['show'] = '' if e['show'] else '\u2022'
        ttk.Button(scrollable_frame, text="\U0001f441", width=3, command=toggle_gl_neo4j_pw).grid(
            row=row, column=2, padx=5, pady=10)
        row += 1

        # --- Separator ---
        ttk.Separator(scrollable_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=20)
        row += 1

        # --- Save to .env option ---
        save_env_var = tk.BooleanVar(value=True)
        self.widgets['rag_guidelines']['save_to_env'] = save_env_var
        save_env_check = ttk.Checkbutton(scrollable_frame, text="Save to .env file (persist across restarts)",
                                         variable=save_env_var)
        save_env_check.grid(row=row, column=0, columnspan=3, sticky="w", pady=5)
        ToolTip(save_env_check, "Write values to your .env file so they persist across application restarts")
        row += 1

        ttk.Label(scrollable_frame, text="Settings saved here also update your .env file for use by all components",
                 foreground="gray").grid(row=row, column=0, columnspan=3, sticky="w", padx=(20, 0))

        scrollable_frame.columnconfigure(1, weight=1)

    def _test_pg_connection(self, url: str, label: str):
        """Test a PostgreSQL connection URL in a background thread.

        Args:
            url: PostgreSQL connection string
            label: Display label for the connection (e.g., 'RAG Database')
        """
        if not url.strip():
            messagebox.showwarning("No URL", f"Please enter a {label} URL first.")
            return

        import threading

        def _test():
            try:
                import psycopg2
                conn = psycopg2.connect(url.strip(), connect_timeout=10)
                conn.close()
                self.dialog.after(0, lambda: messagebox.showinfo(
                    "Connection Successful", f"{label} connection successful."))
            except ImportError:
                # Try psycopg (v3)
                try:
                    import psycopg
                    conn = psycopg.connect(url.strip(), connect_timeout=10)
                    conn.close()
                    self.dialog.after(0, lambda: messagebox.showinfo(
                        "Connection Successful", f"{label} connection successful."))
                except ImportError:
                    self.dialog.after(0, lambda: messagebox.showwarning(
                        "Missing Driver",
                        "Neither psycopg2 nor psycopg is installed.\n"
                        "Install with: pip install psycopg2-binary"))
                except Exception as e:
                    msg = str(e)
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Connection Failed", f"{label} connection failed:\n{msg}"))
            except Exception as e:
                msg = str(e)
                self.dialog.after(0, lambda: messagebox.showerror(
                    "Connection Failed", f"{label} connection failed:\n{msg}"))

        threading.Thread(target=_test, daemon=True).start()
