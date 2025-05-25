@echo off
echo Building Medical Assistant for Windows...

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Build executable
echo Building executable...
pyinstaller medical_assistant.spec --clean

echo.
echo Build complete! Executable is in dist/MedicalAssistant.exe
pause