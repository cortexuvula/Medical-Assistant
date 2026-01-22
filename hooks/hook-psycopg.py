# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg (PostgreSQL driver).

psycopg with the [binary] option includes binary extensions in psycopg_binary
that need to be collected properly for PyInstaller to bundle them.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all psycopg submodules
hiddenimports = collect_submodules('psycopg')
hiddenimports += collect_submodules('psycopg_binary')
hiddenimports += collect_submodules('psycopg_pool')

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
datas += collect_data_files('psycopg_binary')
datas += collect_data_files('psycopg_pool')

# Collect dynamic libraries (C extensions)
binaries = collect_dynamic_libs('psycopg')
binaries += collect_dynamic_libs('psycopg_binary')
binaries += collect_dynamic_libs('psycopg_pool')
