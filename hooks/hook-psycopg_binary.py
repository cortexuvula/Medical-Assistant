# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg_binary (PostgreSQL binary driver).

psycopg_binary contains the compiled C extensions and libpq bindings.
This is the critical package for psycopg to work properly.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all psycopg_binary submodules
hiddenimports = collect_submodules('psycopg_binary')

# Add explicit imports for binary implementation
hiddenimports += [
    'psycopg_binary',
    'psycopg_binary._psycopg',
    'psycopg_binary.pq',
]

# Collect data files
datas = collect_data_files('psycopg_binary')

# Collect dynamic libraries - this is the critical part
# psycopg_binary contains compiled .pyd/.so files
binaries = collect_dynamic_libs('psycopg_binary')
