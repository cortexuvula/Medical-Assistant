# -*- coding: utf-8 -*-
"""
PyInstaller hook for psycopg_binary (PostgreSQL binary driver).

psycopg_binary contains the compiled C extensions and libpq bindings.
This is the critical package for psycopg to work properly.

IMPORTANT: psycopg must be imported before psycopg_binary can be used.
This hook DOES NOT use collect_submodules() because it would fail due to
the import order dependency. Instead, we manually locate and add the files.
"""

import os
import importlib.util

# DO NOT use collect_submodules('psycopg_binary') - it fails because
# psycopg_binary requires psycopg to be imported first.

# List explicit imports - the spec file will handle the rest
hiddenimports = [
    'psycopg',
    'psycopg_binary',
]

# Initialize empty lists - let spec file handle binaries
datas = []
binaries = []

# Try to manually locate psycopg_binary and collect its files
# This works because importlib.util.find_spec doesn't actually import the module
try:
    # First import psycopg so psycopg_binary can be found
    import psycopg

    spec = importlib.util.find_spec('psycopg_binary')
    if spec and spec.origin:
        pkg_dir = os.path.dirname(spec.origin)
        print(f"[hook-psycopg_binary] Found package at: {pkg_dir}")

        # Collect binary extensions (.pyd on Windows, .so on Linux/Mac)
        for f in os.listdir(pkg_dir):
            full_path = os.path.join(pkg_dir, f)
            if f.endswith(('.pyd', '.so')):
                binaries.append((full_path, 'psycopg_binary'))
                print(f"[hook-psycopg_binary] Added binary: {f}")
            elif f.endswith('.py'):
                datas.append((full_path, 'psycopg_binary'))

        # Also check for pq subdirectory which contains additional binaries
        pq_dir = os.path.join(pkg_dir, 'pq')
        if os.path.isdir(pq_dir):
            for f in os.listdir(pq_dir):
                full_path = os.path.join(pq_dir, f)
                if f.endswith(('.pyd', '.so', '.dll')):
                    binaries.append((full_path, 'psycopg_binary/pq'))
                    print(f"[hook-psycopg_binary] Added pq binary: {f}")
                elif f.endswith('.py'):
                    datas.append((full_path, 'psycopg_binary/pq'))

        print(f"[hook-psycopg_binary] Collected {len(binaries)} binaries, {len(datas)} data files")
except Exception as e:
    print(f"[hook-psycopg_binary] Manual collection failed: {e}")
