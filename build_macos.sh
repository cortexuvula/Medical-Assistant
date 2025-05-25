#!/bin/bash
set -e  # Exit on error

echo "Building Medical Assistant for macOS..."

# Clean previous builds
rm -rf dist build

# Download FFmpeg if not present and not skipped
if [ "$SKIP_FFMPEG_DOWNLOAD" = "1" ]; then
    echo "Skipping FFmpeg download in CI environment"
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
pip install -r requirements.txt

# Build executable
echo "Building executable..."
pyinstaller medical_assistant.spec --clean || {
    echo "PyInstaller build failed!"
    echo "Current directory contents:"
    ls -la
    exit 1
}

# Verify the build output
if [ -d "dist/MedicalAssistant.app" ]; then
    echo ""
    echo "Build complete! Application is in dist/MedicalAssistant.app"
    echo "To run: open dist/MedicalAssistant.app"
else
    echo "Error: Expected output dist/MedicalAssistant.app not found!"
    echo "Contents of dist directory:"
    ls -la dist/ || echo "dist directory does not exist"
    exit 1
fi