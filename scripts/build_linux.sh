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

# Install dependencies (use Linux-specific requirements to avoid torch/whisper bloat)
echo "Installing dependencies..."
echo "Note: Using requirements-linux.txt which excludes local Whisper (torch) to reduce build size."
echo "Users who need local Whisper can install it separately: pip install openai-whisper"
pip install --no-cache-dir -r requirements-linux.txt

# Build executable
echo "Building executable..."
pyinstaller medical_assistant.spec --clean --log-level=INFO || {
    echo "PyInstaller build failed!"
    echo "Current directory contents:"
    ls -la
    cd "$INITIAL_DIR"
    exit 1
}

# Verify the build output (onedir mode: dist/MedicalAssistant/MedicalAssistant)
if [ -f "dist/MedicalAssistant/MedicalAssistant" ]; then
    # Copy the launcher script into the app directory
    cp scripts/linux_launcher.sh dist/MedicalAssistant/
    chmod +x dist/MedicalAssistant/linux_launcher.sh
    chmod +x dist/MedicalAssistant/MedicalAssistant

    echo ""
    echo "Build complete! Executable is in dist/MedicalAssistant/MedicalAssistant"
    echo "Directory size: $(du -sh dist/MedicalAssistant)"
    echo ""
    echo "To run the application, use ONE of these methods:"
    echo "1. Using the launcher (recommended): ./dist/MedicalAssistant/linux_launcher.sh"
    echo "2. Direct with cleared environment: unset LD_LIBRARY_PATH && ./dist/MedicalAssistant/MedicalAssistant"
    echo ""
    echo "The launcher ensures system FFmpeg libraries are used correctly."

    # Create tar.gz archive for release distribution
    echo "Creating tar.gz archive..."
    tar -czf dist/MedicalAssistant-Linux.tar.gz -C dist MedicalAssistant
    echo "Archive created: dist/MedicalAssistant-Linux.tar.gz ($(du -h dist/MedicalAssistant-Linux.tar.gz | cut -f1))"
else
    echo "Error: Expected output dist/MedicalAssistant/MedicalAssistant not found!"
    echo "Contents of dist directory:"
    ls -la dist/ || echo "dist directory does not exist"
    cd "$INITIAL_DIR"
    exit 1
fi

# Return to initial directory
cd "$INITIAL_DIR"