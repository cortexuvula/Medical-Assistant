#!/bin/bash
# Install desktop entry for Medical Assistant on Linux

echo "Installing Medical Assistant desktop entry..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create desktop entry from template
DESKTOP_FILE="$HOME/.local/share/applications/medical-assistant.desktop"
mkdir -p "$HOME/.local/share/applications"

# Check if executable exists
if [ -f "$SCRIPT_DIR/dist/MedicalAssistant" ]; then
    EXEC_PATH="$SCRIPT_DIR/dist/MedicalAssistant"
else
    EXEC_PATH="$SCRIPT_DIR/linux_launcher.sh"
fi

# Create the desktop entry
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Medical Assistant
Comment=Voice-powered medical documentation
Exec=$EXEC_PATH
Icon=$SCRIPT_DIR/icon.ico
Terminal=false
Type=Application
Categories=Office;Medical;AudioVideo;
StartupNotify=true
EOF

# Make it executable
chmod +x "$DESKTOP_FILE"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications"
fi

echo "Desktop entry installed successfully!"
echo "You should now see Medical Assistant in your applications menu."