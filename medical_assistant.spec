# -*- mode: python ; coding: utf-8 -*-

import os
import platform
import sys

# Add src to path for collecting submodules
src_path = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'src')
sys.path.insert(0, src_path)

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

# Collect all submodules from internal packages
internal_hiddenimports = []
internal_datas = []
internal_binaries = []
for pkg in ['managers', 'utils', 'core', 'settings', 'database', 'ai', 'audio',
            'processing', 'rag', 'stt_providers', 'tts_providers', 'translation', 'ui']:
    try:
        datas, binaries, hiddenimports = collect_all(pkg)
        internal_hiddenimports += hiddenimports
        internal_datas += datas
        internal_binaries += binaries
        print(f"Collected {len(hiddenimports)} modules from {pkg}")
    except Exception as e:
        print(f"Warning: Could not collect from {pkg}: {e}")
        # Fallback: try collect_submodules only
        try:
            internal_hiddenimports += collect_submodules(pkg)
        except:
            pass

# Collect PostgreSQL driver packages (psycopg with binary extensions)
# IMPORTANT: psycopg must be imported before psycopg_binary can be collected
# This is because psycopg_binary depends on psycopg being loaded first
psycopg_binaries = []
psycopg_datas = []
psycopg_hiddenimports = []

# First, import psycopg to enable psycopg_binary collection
try:
    import psycopg
    print(f"Pre-imported psycopg from: {psycopg.__file__}")
except ImportError as e:
    print(f"Warning: Could not pre-import psycopg: {e}")

# Now collect packages in the correct order
for pkg in ['psycopg', 'psycopg_binary', 'psycopg_pool', 'pgvector']:
    try:
        datas, binaries, hiddenimports = collect_all(pkg)
        psycopg_datas += datas
        psycopg_binaries += binaries
        psycopg_hiddenimports += hiddenimports
        print(f"Collected psycopg package: {pkg} ({len(binaries)} binaries, {len(hiddenimports)} imports)")
    except Exception as e:
        print(f"Warning: Could not collect {pkg}: {e}")

# Fallback: If psycopg_binary wasn't collected, try to manually locate its files
if not any('psycopg_binary' in str(b) for b in psycopg_binaries):
    print("Attempting manual psycopg_binary collection...")
    try:
        import importlib.util
        spec = importlib.util.find_spec('psycopg_binary')
        if spec and spec.origin:
            import os
            pkg_dir = os.path.dirname(spec.origin)
            print(f"Found psycopg_binary at: {pkg_dir}")
            # Collect all .pyd/.so files (binary extensions)
            for f in os.listdir(pkg_dir):
                if f.endswith(('.pyd', '.so', '.dll')):
                    src = os.path.join(pkg_dir, f)
                    psycopg_binaries.append((src, 'psycopg_binary'))
                    print(f"  Added binary: {f}")
            # Collect all .py files as data
            for f in os.listdir(pkg_dir):
                if f.endswith('.py'):
                    src = os.path.join(pkg_dir, f)
                    psycopg_datas.append((src, 'psycopg_binary'))
    except Exception as e:
        print(f"Manual psycopg_binary collection failed: {e}")

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

# Collect Whisper assets explicitly (mel_filters.npz, tokenizer files).
# The hook-whisper.py should also do this, but the hook may not trigger if
# PyInstaller doesn't detect the lazy `import whisper` inside functions.
whisper_datas = []
if platform.system() != 'Linux':
    try:
        whisper_datas = collect_data_files('whisper')
        print(f"Collected {len(whisper_datas)} Whisper data files")
    except Exception as e:
        print(f"Warning: Could not collect Whisper data files: {e}")

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
    binaries=ffmpeg_files + internal_binaries + psycopg_binaries,
    datas=[
        ('env.example', '.'),
        ('hooks/suppress_console.py', '.'),
        ('icon.ico', '.'),
        ('icon256x256.ico', '.'),  # Include as backup
        ('config', 'config'),  # Include config folder and its contents
        ('src', 'src'),  # Include entire src directory
    ] + soundcard_datas + internal_datas + psycopg_datas + whisper_datas,
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
        'PIL._tkinter_finder',
        'PIL._imagingtk',
        'PIL.ImageTk',
        # Local Whisper STT (lazy-imported inside functions, so PyInstaller
        # misses it and never triggers hook-whisper.py for asset collection)
        'whisper',
        'whisper.audio',
        'whisper.transcribe',
        # PostgreSQL driver for Neon RAG
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
        # pgvector for PostgreSQL vector operations
        'pgvector',
        'pgvector.psycopg',
    ] + internal_hiddenimports + psycopg_hiddenimports,  # Add all internal modules collected above
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
            'CFBundleIconFile': 'icon.icns',
            'NSMicrophoneUsageDescription': 'This app requires microphone access for voice input.',
            # Prevent multiple instances and handle reopen events properly
            'LSMultipleInstancesProhibited': True,
            # Allow the app to be brought to foreground when relaunched
            'NSSupportsAutomaticGraphicsSwitching': True,
            # Set minimum macOS version
            'LSMinimumSystemVersion': '10.15',
            # Enable high-resolution icon rendering
            'NSHighResolutionCapable': True,
        },
    )