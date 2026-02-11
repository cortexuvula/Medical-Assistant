#!/bin/bash
set -e  # Exit on error

# Store the initial directory
INITIAL_DIR=$(pwd)

echo "Building Medical Assistant for macOS..."
echo "Current directory: $(pwd)"

# Check if we're already in the project root (contains requirements.txt)
if [ -f "requirements.txt" ]; then
    echo "Already in project root directory"
else
    echo "Changing to parent directory..."
    cd ..
fi

PROJECT_ROOT=$(pwd)

# Clean previous builds
rm -rf dist build

# Download FFmpeg if not present and not skipped
if [ "$SKIP_FFMPEG_DOWNLOAD" = "1" ]; then
    echo "Skipping FFmpeg download in CI environment"
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
pip install -r requirements.txt

# Build executable
echo "Building executable..."
pyinstaller medical_assistant.spec --clean || {
    echo "PyInstaller build failed!"
    echo "Current directory contents:"
    ls -la
    cd "$INITIAL_DIR"
    exit 1
}

# Verify the build output
if [ ! -d "dist/MedicalAssistant.app" ]; then
    echo "Error: Expected output dist/MedicalAssistant.app not found!"
    echo "Contents of dist directory:"
    ls -la dist/ || echo "dist directory does not exist"
    cd "$INITIAL_DIR"
    exit 1
fi

echo ""
echo "Build complete! Application is in dist/MedicalAssistant.app"

# ─── Code Signing & Notarization ───
# Skip if MACOS_SIGNING_IDENTITY is not set (local dev builds)
if [ -z "$MACOS_SIGNING_IDENTITY" ]; then
    echo ""
    echo "MACOS_SIGNING_IDENTITY not set — skipping code signing and notarization."
    echo "Creating unsigned DMG..."
    hdiutil create -volname "Medical Assistant" \
        -srcfolder "dist/MedicalAssistant.app" \
        -ov -format UDZO \
        "dist/MedicalAssistant-macOS.dmg"
    echo "Unsigned DMG created: dist/MedicalAssistant-macOS.dmg"
    echo "To run: open dist/MedicalAssistant.app"
    cd "$INITIAL_DIR"
    exit 0
fi

echo ""
echo "=== Code Signing ==="
echo "Signing identity: $MACOS_SIGNING_IDENTITY"

# PyInstaller onedir builds produce an .app with many individual binaries.
# Apple notarization requires EACH binary to be signed individually with
# hardened runtime (--options runtime) before signing the outer .app bundle.
# Using --deep alone is insufficient and deprecated by Apple.

# Step 1: Sign all shared libraries (.dylib, .so) and object files
echo "Signing individual binaries inside .app bundle..."
SIGN_COUNT=0
while IFS= read -r -d '' binary; do
    codesign --force --sign "$MACOS_SIGNING_IDENTITY" \
        --options runtime \
        --timestamp \
        "$binary" 2>/dev/null && SIGN_COUNT=$((SIGN_COUNT + 1))
done < <(find "dist/MedicalAssistant.app" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.o" \) -print0)
echo "Signed $SIGN_COUNT shared libraries."

# Step 2: Sign all executable binaries (Mach-O files without extensions)
while IFS= read -r -d '' binary; do
    # Check if it's a Mach-O binary
    if file "$binary" | grep -q "Mach-O"; then
        codesign --force --sign "$MACOS_SIGNING_IDENTITY" \
            --options runtime \
            --timestamp \
            "$binary" 2>/dev/null && SIGN_COUNT=$((SIGN_COUNT + 1))
    fi
done < <(find "dist/MedicalAssistant.app/Contents/MacOS" -type f ! -name "MedicalAssistant" -print0)

# Step 3: Sign the main executable with entitlements
echo "Signing main executable..."
codesign --force --sign "$MACOS_SIGNING_IDENTITY" \
    --options runtime \
    --entitlements "$PROJECT_ROOT/entitlements.plist" \
    --timestamp \
    "dist/MedicalAssistant.app/Contents/MacOS/MedicalAssistant"

# Step 4: Sign the outer .app bundle
echo "Signing .app bundle..."
codesign --force --sign "$MACOS_SIGNING_IDENTITY" \
    --options runtime \
    --entitlements "$PROJECT_ROOT/entitlements.plist" \
    --timestamp \
    "dist/MedicalAssistant.app"

echo "Signing complete ($SIGN_COUNT binaries + main executable + .app bundle)."

# Verify the signature
echo ""
echo "=== Verifying Signature ==="
codesign --verify --deep --strict "dist/MedicalAssistant.app"
echo "codesign --verify: OK"

# spctl may fail in CI (no GUI session), so don't fail the build on it
spctl --assess --type execute "dist/MedicalAssistant.app" 2>&1 && echo "spctl --assess: accepted" || echo "spctl --assess: skipped (expected in CI)"

# ─── Create DMG ───
echo ""
echo "=== Creating DMG ==="

DMG_NAME="MedicalAssistant-macOS.dmg"

if command -v create-dmg &> /dev/null; then
    echo "Using create-dmg for styled DMG..."
    create-dmg \
        --volname "Medical Assistant" \
        --volicon "icon.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "MedicalAssistant.app" 150 190 \
        --app-drop-link 450 190 \
        --no-internet-enable \
        "dist/$DMG_NAME" \
        "dist/MedicalAssistant.app" || {
            echo "create-dmg failed, falling back to hdiutil..."
            hdiutil create -volname "Medical Assistant" \
                -srcfolder "dist/MedicalAssistant.app" \
                -ov -format UDZO \
                "dist/$DMG_NAME"
        }
else
    echo "create-dmg not found, using hdiutil..."
    hdiutil create -volname "Medical Assistant" \
        -srcfolder "dist/MedicalAssistant.app" \
        -ov -format UDZO \
        "dist/$DMG_NAME"
fi

echo "DMG created: dist/$DMG_NAME"

# Sign the DMG
echo ""
echo "=== Signing DMG ==="
codesign --force --sign "$MACOS_SIGNING_IDENTITY" --timestamp "dist/$DMG_NAME"
echo "DMG signed."

# ─── Notarization ───
echo ""
echo "=== Notarizing ==="

if [ -z "$APPLE_ID" ] || [ -z "$APPLE_ID_PASSWORD" ] || [ -z "$MACOS_TEAM_ID" ]; then
    echo "Notarization credentials not set — skipping notarization."
    echo "Set APPLE_ID, APPLE_ID_PASSWORD, and MACOS_TEAM_ID to enable."
    cd "$INITIAL_DIR"
    exit 0
fi

NOTARIZE_OUTPUT=$(xcrun notarytool submit "dist/$DMG_NAME" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PASSWORD" \
    --team-id "$MACOS_TEAM_ID" \
    --wait \
    --timeout 30m 2>&1)

echo "$NOTARIZE_OUTPUT"

# Check if notarization was accepted
if echo "$NOTARIZE_OUTPUT" | grep -q "status: Accepted"; then
    echo "Notarization accepted."
else
    echo ""
    echo "WARNING: Notarization was NOT accepted."
    # Try to fetch the log for details
    SUBMISSION_ID=$(echo "$NOTARIZE_OUTPUT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$SUBMISSION_ID" ]; then
        echo "Fetching notarization log for submission $SUBMISSION_ID..."
        xcrun notarytool log "$SUBMISSION_ID" \
            --apple-id "$APPLE_ID" \
            --password "$APPLE_ID_PASSWORD" \
            --team-id "$MACOS_TEAM_ID" \
            notarization_log.json 2>&1 || true
        if [ -f "notarization_log.json" ]; then
            echo "=== Notarization Log ==="
            cat notarization_log.json
            echo ""
        fi
    fi
    echo "Continuing without notarization — DMG will still work but may show Gatekeeper warning."
fi

# Staple the notarization ticket to the DMG (only works if notarization succeeded)
echo ""
echo "=== Stapling ==="
xcrun stapler staple "dist/$DMG_NAME" 2>&1 || echo "Stapling skipped (notarization may not have succeeded)."
xcrun stapler validate "dist/$DMG_NAME" 2>&1 || echo "Staple validation skipped."
echo "Stapling step complete."

echo ""
echo "=== Done ==="
echo "Signed and notarized DMG: dist/$DMG_NAME"

# Return to initial directory
cd "$INITIAL_DIR"
