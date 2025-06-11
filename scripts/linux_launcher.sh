#!/bin/bash
# Launcher script for Medical Assistant on Linux
# This ensures system libraries are used for FFmpeg

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Clear LD_LIBRARY_PATH to prevent conflicts with bundled libraries
unset LD_LIBRARY_PATH

# Run the application
exec "$SCRIPT_DIR/MedicalAssistant" "$@"