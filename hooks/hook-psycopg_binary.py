# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg_binary (PostgreSQL binary driver).

psycopg_binary contains the compiled C extensions and libpq bindings.
This is the critical package for psycopg to work properly.

IMPORTANT: psycopg must be imported before psycopg_binary can be used.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Import psycopg first - this is required before psycopg_binary can be accessed
try:
    import psycopg
except ImportError:
    pass

# Now collect psycopg_binary submodules
try:
    hiddenimports = collect_submodules('psycopg_binary')
except Exception:
    hiddenimports = []

# Add explicit imports for binary implementation
hiddenimports += [
    'psycopg',  # Must be imported first
    'psycopg_binary',
    'psycopg_binary._psycopg',
    'psycopg_binary.pq',
]

# Collect data files
try:
    datas = collect_data_files('psycopg_binary')
except Exception:
    datas = []

# Collect dynamic libraries - this is the critical part
# psycopg_binary contains compiled .pyd/.so files
try:
    binaries = collect_dynamic_libs('psycopg_binary')
except Exception:
    binaries = []
