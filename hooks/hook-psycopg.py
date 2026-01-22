# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg (PostgreSQL driver).

psycopg with the [binary] option includes binary extensions in psycopg_binary
that need to be collected properly for PyInstaller to bundle them.

This hook handles psycopg and its submodules. For psycopg_binary, see
hook-psycopg_binary.py which handles it separately to avoid import order issues.
"""

import os
import importlib.util
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all psycopg submodules
hiddenimports = collect_submodules('psycopg')

# DO NOT call collect_submodules('psycopg_binary') here - it will fail
# because psycopg needs to be imported first. hook-psycopg_binary.py handles this.

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

# Collect data files from psycopg
datas = collect_data_files('psycopg')

# Collect dynamic libraries from psycopg
binaries = collect_dynamic_libs('psycopg')

# Also try to manually collect psycopg_binary binaries
try:
    import psycopg  # Import psycopg first

    spec = importlib.util.find_spec('psycopg_binary')
    if spec and spec.origin:
        pkg_dir = os.path.dirname(spec.origin)
        print(f"[hook-psycopg] Found psycopg_binary at: {pkg_dir}")

        for f in os.listdir(pkg_dir):
            full_path = os.path.join(pkg_dir, f)
            if f.endswith(('.pyd', '.so')):
                binaries.append((full_path, 'psycopg_binary'))
                print(f"[hook-psycopg] Added psycopg_binary: {f}")

        # Check pq subdirectory
        pq_dir = os.path.join(pkg_dir, 'pq')
        if os.path.isdir(pq_dir):
            for f in os.listdir(pq_dir):
                full_path = os.path.join(pq_dir, f)
                if f.endswith(('.pyd', '.so', '.dll')):
                    binaries.append((full_path, 'psycopg_binary/pq'))

except Exception as e:
    print(f"[hook-psycopg] Could not collect psycopg_binary: {e}")
