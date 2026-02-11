@echo off
setlocal enabledelayedexpansion

echo Building Medical Assistant for Windows...
echo Python location: %pythonLocation%
echo Current directory: %CD%

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Download FFmpeg if not present
if not exist "..\ffmpeg\ffmpeg.exe" (
    echo Downloading FFmpeg...
    cd ..
    call python scripts\download_ffmpeg.py
    cd scripts
    if !errorlevel! neq 0 (
        echo Warning: FFmpeg download failed. Build will continue without bundled FFmpeg.
    )
)

REM Install dependencies
echo Installing dependencies...
call python -m pip install --upgrade pip
call python -m pip install --no-cache-dir -r requirements.txt
if !errorlevel! neq 0 (
    echo Failed to install dependencies!
    exit /b 1
)

REM Verify PyInstaller is installed
echo Verifying PyInstaller installation...
call python -m pip show pyinstaller
if !errorlevel! neq 0 (
    echo PyInstaller not found, installing...
    call python -m pip install pyinstaller
)

REM Build executable
echo Building executable...
cd ..
call python -m PyInstaller medical_assistant.spec --clean --noconfirm
if !errorlevel! neq 0 (
    echo PyInstaller build failed!
    cd scripts
    exit /b 1
)
cd scripts

REM Verify the build output (onedir mode: dist\MedicalAssistant\MedicalAssistant.exe)
if exist "dist\MedicalAssistant\MedicalAssistant.exe" (
    echo.
    echo Build complete! Executable is in dist\MedicalAssistant\MedicalAssistant.exe
    dir dist\MedicalAssistant\MedicalAssistant.exe
) else (
    echo Error: Expected output dist\MedicalAssistant\MedicalAssistant.exe not found!
    if exist dist (
        echo Contents of dist directory:
        dir dist
    )
    exit /b 1
)