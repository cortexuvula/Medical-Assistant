# -*- coding: utf-8 -*-
"""
PyInstaller hook for pgvector (PostgreSQL vector operations).

pgvector provides Python bindings for the pgvector PostgreSQL extension
used for vector similarity search.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all pgvector submodules
hiddenimports = collect_submodules('pgvector')

# Add explicit imports
hiddenimports += [
    'pgvector',
    'pgvector.psycopg',
    'pgvector.sqlalchemy',
    'pgvector.utils',
]

# Collect data files
datas = collect_data_files('pgvector')
