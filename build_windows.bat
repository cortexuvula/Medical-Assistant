@echo off
echo Building Medical Assistant for Windows...

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Install dependencies
echo Installing dependencies...
python -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies!
    exit /b 1
)

REM Build executable
echo Building executable...
python -m PyInstaller medical_assistant.spec --clean
if errorlevel 1 (
    echo PyInstaller build failed!
    exit /b 1
)

REM Verify the build output
if exist "dist\MedicalAssistant.exe" (
    echo.
    echo Build complete! Executable is in dist\MedicalAssistant.exe
    dir dist\MedicalAssistant.exe
) else (
    echo Error: Expected output dist\MedicalAssistant.exe not found!
    dir dist
    exit /b 1
)