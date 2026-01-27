"""PyInstaller hook for tiktoken.

tiktoken uses a plugin/registry system (tiktoken_ext.openai_public) to register
encoding constructors like cl100k_base and o200k_base.  PyInstaller does not
detect this namespace-package plugin automatically, so we must explicitly collect
the data files (BPE vocab files) and hidden imports.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect tiktoken's own data (compiled Rust extension, etc.)
datas = collect_data_files("tiktoken")

# Collect the tiktoken_ext plugin that registers encoding names
hiddenimports = collect_submodules("tiktoken_ext")
