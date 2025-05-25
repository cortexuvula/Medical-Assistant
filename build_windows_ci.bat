@echo off
REM Special batch file for CI/CD environments to avoid prompts

echo Building Medical Assistant for Windows (CI Mode)...
echo Python: %PYTHON%
echo Current directory: %CD%

REM Clean previous builds
if exist dist rd /s /q dist 2>nul
if exist build rd /s /q build 2>nul

REM Install dependencies
echo Installing dependencies...
%PYTHON% -m pip install --upgrade pip
if %errorlevel% neq 0 exit /b %errorlevel%

%PYTHON% -m pip install --no-cache-dir -r requirements.txt
if %errorlevel% neq 0 exit /b %errorlevel%

REM Verify PyInstaller
%PYTHON% -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    %PYTHON% -m pip install pyinstaller
    if %errorlevel% neq 0 exit /b %errorlevel%
)

REM Build with PyInstaller
echo Building executable...
%PYTHON% -m PyInstaller medical_assistant.spec --clean --noconfirm --log-level=WARN
if %errorlevel% neq 0 exit /b %errorlevel%

REM Check output
if exist "dist\MedicalAssistant.exe" (
    echo Build successful!
    dir dist\MedicalAssistant.exe
    exit /b 0
) else (
    echo Build failed - executable not found
    if exist dist dir dist
    exit /b 1
)