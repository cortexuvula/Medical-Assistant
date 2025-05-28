#!/bin/bash
set -e  # Exit on error

echo "Building Medical Assistant for Linux..."
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

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
        python download_ffmpeg.py
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
    exit 1
}

# Verify the build output
if [ -f "dist/MedicalAssistant" ]; then
    echo ""
    echo "Build complete! Executable is in dist/MedicalAssistant"
    echo "Executable size: $(du -h dist/MedicalAssistant)"
    echo "To run: ./dist/MedicalAssistant"
else
    echo "Error: Expected output dist/MedicalAssistant not found!"
    echo "Contents of dist directory:"
    ls -la dist/ || echo "dist directory does not exist"
    exit 1
fi