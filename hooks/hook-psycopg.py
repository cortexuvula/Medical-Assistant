# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg (PostgreSQL driver).

psycopg with the [binary] option includes binary extensions in psycopg_binary
that need to be collected properly for PyInstaller to bundle them.

This hook handles psycopg, psycopg_binary, and psycopg_pool together because
psycopg must be imported before psycopg_binary can be accessed.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all psycopg submodules first
hiddenimports = collect_submodules('psycopg')

# Import psycopg before collecting psycopg_binary (required by psycopg_binary)
try:
    import psycopg
    # Now we can safely collect psycopg_binary
    hiddenimports += collect_submodules('psycopg_binary')
except ImportError:
    pass

# psycopg_pool is a separate module
try:
    hiddenimports += collect_submodules('psycopg_pool')
except Exception:
    pass

# Add explicit imports for commonly missed modules
hiddenimports += [
    'psycopg',
    'psycopg.adapt',
    'psycopg.copy',
    'psycopg.cursor',
    'psycopg.errors',
    'psycopg.pq',
    'psycopg.rows',
    'psycopg.sql',
    'psycopg.types',
    'psycopg.types.json',
    'psycopg.types.numeric',
    'psycopg._dns',
    'psycopg._compat',
    'psycopg_pool',
    'psycopg_binary',
    # Low-level pq bindings
    'psycopg.pq._pq_ctypes',
    'psycopg.pq.pq_ctypes',
]

# Collect data files
datas = collect_data_files('psycopg')
try:
    import psycopg  # Ensure psycopg is imported before accessing psycopg_binary
    datas += collect_data_files('psycopg_binary')
except Exception:
    pass

# Collect dynamic libraries (C extensions)
binaries = collect_dynamic_libs('psycopg')
try:
    import psycopg  # Ensure psycopg is imported before accessing psycopg_binary
    binaries += collect_dynamic_libs('psycopg_binary')
except Exception:
    pass
