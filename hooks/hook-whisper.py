# -*- coding: utf-8 -*-
"""
PyInstaller hook for openai-whisper.

Whisper requires data files (mel_filters.npz, tokenizer files) that
are not collected automatically by PyInstaller.
"""

from PyInstaller.utils.hooks import collect_data_files

# Collect whisper's assets directory (mel_filters.npz, gpt2.tiktoken, etc.)
datas = collect_data_files('whisper')
