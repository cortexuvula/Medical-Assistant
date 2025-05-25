#!/bin/bash

echo "Building Medical Assistant for macOS..."

# Clean previous builds
rm -rf dist build

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Build executable
echo "Building executable..."
pyinstaller medical_assistant.spec --clean

echo ""
echo "Build complete! Application is in dist/MedicalAssistant.app"
echo "To run: open dist/MedicalAssistant.app"