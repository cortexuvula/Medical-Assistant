# -*- coding: utf-8 -*-
"""
PyInstaller hook for deepgram-sdk.

The Deepgram SDK v3 has a complex module structure that requires
collecting all submodules for proper bundling.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all deepgram submodules
hiddenimports = collect_submodules('deepgram')

# Collect any data files (e.g., version files)
datas = collect_data_files('deepgram')
