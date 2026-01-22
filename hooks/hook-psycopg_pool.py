# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg_pool (PostgreSQL connection pooling).

psycopg_pool depends on psycopg, so we need to ensure both are collected.
Note: psycopg_pool is NOT a package (it's a single module), so we can't use
collect_submodules, collect_data_files, or collect_dynamic_libs on it.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Import psycopg first (required for psycopg_binary)
try:
    import psycopg
except ImportError:
    pass

# psycopg_pool depends on psycopg, so collect psycopg submodules
hiddenimports = collect_submodules('psycopg')

# Collect psycopg_binary after importing psycopg
try:
    hiddenimports += collect_submodules('psycopg_binary')
except Exception:
    pass

# Explicitly list required imports
# Note: psycopg_pool is a single module, not a package with submodules
hiddenimports += [
    'psycopg_pool',
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
    'psycopg_binary',
]

# Collect data files from psycopg packages
datas = collect_data_files('psycopg')
try:
    datas += collect_data_files('psycopg_binary')
except Exception:
    pass

# Collect dynamic libraries (C extensions)
binaries = collect_dynamic_libs('psycopg')
try:
    binaries += collect_dynamic_libs('psycopg_binary')
except Exception:
    pass
