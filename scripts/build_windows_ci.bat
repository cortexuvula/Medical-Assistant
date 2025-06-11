@echo off
REM Special batch file for CI/CD environments to avoid prompts
setlocal

echo Building Medical Assistant for Windows (CI Mode)...
echo Python: %PYTHON%
echo Current directory: %CD%

REM Change to parent directory to be at project root
cd ..

REM Clean previous builds
if exist dist rd /s /q dist 2>nul
if exist build rd /s /q build 2>nul

REM Download FFmpeg if not present and not skipped
if "%SKIP_FFMPEG_DOWNLOAD%"=="1" (
    echo Skipping FFmpeg download in CI environment
) else (
    if not exist "ffmpeg\ffmpeg.exe" (
        echo Downloading FFmpeg...
        %PYTHON% scripts\download_ffmpeg.py
        if %errorlevel% neq 0 (
            echo Warning: FFmpeg download failed. Build will continue without bundled FFmpeg.
        )
    )
)

REM Install dependencies
echo Installing dependencies...
echo Upgrading pip...
%PYTHON% -m pip install --upgrade pip --no-warn-script-location
if %errorlevel% neq 0 (
    cd scripts
    exit /b %errorlevel%
)

echo Installing requirements...
%PYTHON% -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
if %errorlevel% neq 0 (
    cd scripts
    exit /b %errorlevel%
)

REM Verify PyInstaller
%PYTHON% -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    %PYTHON% -m pip install pyinstaller
    if %errorlevel% neq 0 (
        cd scripts
        exit /b %errorlevel%
    )
)

REM Build with PyInstaller
echo Building executable...
%PYTHON% -m PyInstaller medical_assistant.spec --clean --noconfirm --log-level=WARN
if %errorlevel% neq 0 (
    cd scripts
    exit /b %errorlevel%
)

REM Check output
if exist "dist\MedicalAssistant.exe" (
    echo Build successful!
    dir dist\MedicalAssistant.exe
    cd scripts
    exit /b 0
) else (
    echo Build failed - executable not found
    if exist dist dir dist
    cd scripts
    exit /b 1
)