# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg_pool (PostgreSQL connection pooling).

psycopg_pool depends on psycopg, so we need to ensure both are collected.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect psycopg_pool submodules
hiddenimports = collect_submodules('psycopg_pool')

# psycopg_pool depends on psycopg, so collect those too
hiddenimports += collect_submodules('psycopg')
hiddenimports += collect_submodules('psycopg_binary')

# Explicitly list required imports
hiddenimports += [
    'psycopg_pool',
    'psycopg_pool.pool',
    'psycopg_pool.sched',
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

# Collect data files
datas = collect_data_files('psycopg_pool')
datas += collect_data_files('psycopg')
datas += collect_data_files('psycopg_binary')

# Collect dynamic libraries (C extensions)
binaries = collect_dynamic_libs('psycopg')
binaries += collect_dynamic_libs('psycopg_binary')
binaries += collect_dynamic_libs('psycopg_pool')
