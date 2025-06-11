"""
PyInstaller hook for soundcard module
"""
from PyInstaller.utils.hooks import collect_data_files

# Collect all data files from soundcard, including .h files
datas = collect_data_files('soundcard', include_py_files=False)