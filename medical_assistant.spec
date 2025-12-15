# -*- mode: python ; coding: utf-8 -*-

import os
import platform

# Determine FFmpeg files based on platform
ffmpeg_files = []
ffmpeg_dir = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'ffmpeg')

# Only bundle FFmpeg for Windows and macOS, not Linux
if os.path.exists(ffmpeg_dir) and platform.system() != 'Linux':
    if platform.system() == 'Windows':
        ffmpeg_files = [
            (os.path.join(ffmpeg_dir, 'ffmpeg.exe'), 'ffmpeg'),
            (os.path.join(ffmpeg_dir, 'ffprobe.exe'), 'ffmpeg'),
        ]
    else:  # macOS
        ffmpeg_files = [
            (os.path.join(ffmpeg_dir, 'ffmpeg'), 'ffmpeg'),
        ]
        ffprobe_path = os.path.join(ffmpeg_dir, 'ffprobe')
        if os.path.exists(ffprobe_path):
            ffmpeg_files.append((ffprobe_path, 'ffmpeg'))

# Find soundcard module path
import importlib.util
soundcard_spec = importlib.util.find_spec('soundcard')
soundcard_datas = []
if soundcard_spec and soundcard_spec.origin:
    soundcard_path = os.path.dirname(soundcard_spec.origin)
    # Include all .h files from soundcard
    for h_file in ['pulseaudio.py.h', 'coreaudio.py.h', 'mediafoundation.py.h']:
        h_path = os.path.join(soundcard_path, h_file)
        if os.path.exists(h_path):
            soundcard_datas.append((h_path, 'soundcard'))

# Exclude heavy packages on Linux to avoid build size issues
# Users who need local Whisper on Linux can install torch separately
linux_excludes = [
    'torch', 'torchvision', 'torchaudio',
    'triton',
    'nvidia', 'nvidia.cuda_runtime', 'nvidia.cudnn', 'nvidia.cublas',
    'nvidia.cufft', 'nvidia.curand', 'nvidia.cusolver', 'nvidia.cusparse',
    'nvidia.nccl', 'nvidia.nvtx', 'nvidia.nvjitlink', 'nvidia.cuda_nvrtc',
    'nvidia.cuda_cupti', 'nvidia.cusparselt', 'nvidia.nvshmem', 'nvidia.cufile',
    'whisper', 'openai-whisper',
    'numba', 'llvmlite',
] if platform.system() == 'Linux' else []

a = Analysis(
    ['main.py'],
    pathex=['src'],  # Add src to path
    binaries=ffmpeg_files,
    datas=[
        ('env.example', '.'),
        ('hooks/suppress_console.py', '.'),
        ('icon.ico', '.'),
        ('icon256x256.ico', '.'),  # Include as backup
        ('config', 'config'),  # Include config folder and its contents
    ] + soundcard_datas,
    hiddenimports=[
        'tkinter',
        'ttkbootstrap',
        'speech_recognition',
        'pydub',
        # Deepgram SDK v3 modules
        'deepgram',
        'deepgram.clients',
        'deepgram.clients.prerecorded',
        'deepgram.clients.prerecorded.v1',
        'deepgram.clients.prerecorded.v1.client',
        'deepgram.clients.prerecorded.v1.options',
        'deepgram.clients.listen',
        'deepgram.clients.listen.v1',
        'deepgram.clients.listen.v1.rest',
        'deepgram.options',
        'deepgram.client',
        'openai',
        'pyaudio',
        'soundcard',
        'sounddevice',
        'groq',
        'src.stt_providers',
        'src.stt_providers.base',
        'src.stt_providers.deepgram',
        'src.stt_providers.elevenlabs',
        'src.stt_providers.groq',
        'src.stt_providers.whisper',
        'PIL._tkinter_finder',
        'PIL._imagingtk',
        'PIL.ImageTk',
    ],
    hookspath=['.', 'hooks'],  # Look for hooks in current directory and hooks folder
    hooksconfig={},
    runtime_hooks=['hooks/runtime_hook_linux.py'] if platform.system() == 'Linux' else (['hooks/runtime_hook_windows.py'] if platform.system() == 'Windows' else []),
    excludes=linux_excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MedicalAssistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want console output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if platform.system() == 'Windows' else ('icon.icns' if platform.system() == 'Darwin' else None),
)

# For macOS, create an app bundle
import sys
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='MedicalAssistant.app',
        icon='icon.icns',
        bundle_identifier='com.medicalassistant.app',
        info_plist={
            'NSMicrophoneUsageDescription': 'This app requires microphone access for voice input.',
        },
    )