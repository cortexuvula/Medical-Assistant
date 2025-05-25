#!/bin/bash

echo "Building Medical Assistant for Linux..."

# Clean previous builds
rm -rf dist build

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Build executable
echo "Building executable..."
pyinstaller medical_assistant.spec --clean

echo ""
echo "Build complete! Executable is in dist/MedicalAssistant"
echo "To run: ./dist/MedicalAssistant"