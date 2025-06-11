#!/bin/bash
set -e  # Exit on error

# Store the initial directory
INITIAL_DIR=$(pwd)

echo "Building Medical Assistant for Linux..."
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Check if we're already in the project root (contains requirements.txt)
if [ -f "requirements.txt" ]; then
    echo "Already in project root directory"
else
    echo "Changing to parent directory..."
    cd ..
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist build

# Note about FFmpeg on Linux
echo "Note: Linux builds use system FFmpeg to avoid library dependency issues."
echo "Please ensure FFmpeg is installed: sudo apt-get install ffmpeg (on Ubuntu/Debian)"
echo ""

# Skip FFmpeg download for Linux as we'll use system version
if [ "$SKIP_FFMPEG_DOWNLOAD" = "1" ] || [ "$(uname)" = "Linux" ]; then
    echo "Skipping FFmpeg download on Linux (using system FFmpeg)"
else
    if [ ! -d "ffmpeg" ] || [ ! -f "ffmpeg/ffmpeg" ]; then
        echo "Downloading FFmpeg..."
        python scripts/download_ffmpeg.py
        if [ $? -ne 0 ]; then
            echo "Warning: FFmpeg download failed. Build will continue without bundled FFmpeg."
        fi
    fi
fi

# Install dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Build executable
echo "Building executable..."
pyinstaller medical_assistant.spec --clean --log-level=INFO || {
    echo "PyInstaller build failed!"
    echo "Current directory contents:"
    ls -la
    cd "$INITIAL_DIR"
    exit 1
}

# Verify the build output
if [ -f "dist/MedicalAssistant" ]; then
    # Copy the launcher script to dist
    cp scripts/linux_launcher.sh dist/
    chmod +x dist/linux_launcher.sh
    
    echo ""
    echo "Build complete! Executable is in dist/MedicalAssistant"
    echo "Executable size: $(du -h dist/MedicalAssistant)"
    echo ""
    echo "To run the application, use ONE of these methods:"
    echo "1. Using the launcher (recommended): ./dist/linux_launcher.sh"
    echo "2. Direct with cleared environment: unset LD_LIBRARY_PATH && ./dist/MedicalAssistant"
    echo ""
    echo "The launcher ensures system FFmpeg libraries are used correctly."
else
    echo "Error: Expected output dist/MedicalAssistant not found!"
    echo "Contents of dist directory:"
    ls -la dist/ || echo "dist directory does not exist"
    cd "$INITIAL_DIR"
    exit 1
fi

# Return to initial directory
cd "$INITIAL_DIR"