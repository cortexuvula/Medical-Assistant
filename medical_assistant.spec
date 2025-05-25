# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('env.example', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'ttkbootstrap',
        'speech_recognition',
        'pydub',
        'deepgram',
        'openai',
        'pyaudio',
        'soundcard',
        'sounddevice',
        'groq',
        'stt_providers',
        'stt_providers.base',
        'stt_providers.deepgram',
        'stt_providers.elevenlabs',
        'stt_providers.groq',
        'stt_providers.whisper',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    icon=None,  # Add your icon file path here if you have one
)

# For macOS, create an app bundle
import sys
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='MedicalAssistant.app',
        icon=None,  # Add your icon file path here if you have one
        bundle_identifier='com.medicalassistant.app',
        info_plist={
            'NSMicrophoneUsageDescription': 'This app requires microphone access for voice input.',
        },
    )