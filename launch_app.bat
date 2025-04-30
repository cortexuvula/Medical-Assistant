@echo off
setlocal EnableDelayedExpansion

echo Medical Dictation Application Launcher
echo ======================================

REM Set the path to the Python virtual environment
set ENV_DIR=venv

REM Check if the Python command is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if the virtual environment exists
if not exist %ENV_DIR%\Scripts\python.exe (
    echo Virtual environment not found. Creating new environment...
    python -m venv %ENV_DIR%
    
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create virtual environment. Please check your Python installation.
        pause
        exit /b 1
    )
    
    echo Virtual environment created successfully.
) else (
    echo Found existing virtual environment.
)

REM Activate the virtual environment and install requirements
echo Activating virtual environment and ensuring dependencies are installed...
call %ENV_DIR%\Scripts\activate.bat

REM Check if pip needs to be upgraded
%ENV_DIR%\Scripts\python -m pip install --upgrade pip

REM Install requirements
if exist requirements.txt (
    echo Installing requirements from requirements.txt...
    %ENV_DIR%\Scripts\pip install -r requirements.txt
    
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install requirements. Please check requirements.txt and your internet connection.
        pause
        exit /b 1
    )
) else (
    echo Warning: requirements.txt not found. Continuing anyway...
)

REM Check for .env file and notify if it doesn't exist
if not exist .env (
    echo Note: No .env file found. The application will prompt you to set up API keys on first run.
)

REM Launch the application
echo Starting Medical Dictation application...
%ENV_DIR%\Scripts\python app.py

REM If the application crashes or exits with an error, show the message and wait
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo The application exited with an error (code %ERRORLEVEL%).
    echo Please check the log files for more information.
    pause
)

REM Deactivate the virtual environment
call %ENV_DIR%\Scripts\deactivate.bat

exit /b 0
