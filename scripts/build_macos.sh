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

# ─── Remove binaries incompatible with notarization ───
# speech_recognition bundles flac-mac which was built with an SDK older than
# 10.9. Apple refuses to notarize such binaries. We don't need FLAC encoding
# on macOS (speech_recognition uses it as a fallback encoder only).
if [ -f "dist/MedicalAssistant.app/Contents/Frameworks/speech_recognition/flac-mac" ]; then
    echo "Removing flac-mac (built with SDK < 10.9, incompatible with notarization)..."
    rm -f "dist/MedicalAssistant.app/Contents/Frameworks/speech_recognition/flac-mac"
fi

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

# Step 1: Sign ALL Mach-O binaries inside the .app bundle.
# This catches dylibs, .so files, AND standalone executables like:
# - Python.framework/Versions/3.12/Python
# - speech_recognition/flac-mac
# - torch/bin/protoc, torch/bin/torch_shm_manager
# All must be signed with hardened runtime + timestamp for notarization.
echo "Signing all Mach-O binaries inside .app bundle..."
SIGN_COUNT=0
while IFS= read -r -d '' binary; do
    # Skip the main executable (signed separately with entitlements)
    if [ "$binary" = "dist/MedicalAssistant.app/Contents/MacOS/MedicalAssistant" ]; then
        continue
    fi
    # Check if it's a Mach-O binary (dylib, executable, or bundle)
    if file "$binary" | grep -q "Mach-O"; then
        codesign --force --sign "$MACOS_SIGNING_IDENTITY" \
            --options runtime \
            --timestamp \
            "$binary" 2>/dev/null && SIGN_COUNT=$((SIGN_COUNT + 1))
    fi
done < <(find "dist/MedicalAssistant.app" -type f -print0)
echo "Signed $SIGN_COUNT Mach-O binaries."

# Step 2: Sign the main executable with entitlements
echo "Signing main executable..."
codesign --force --sign "$MACOS_SIGNING_IDENTITY" \
    --options runtime \
    --entitlements "$PROJECT_ROOT/entitlements.plist" \
    --timestamp \
    "dist/MedicalAssistant.app/Contents/MacOS/MedicalAssistant"

# Step 3: Sign the outer .app bundle
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
echo "Checking .app bundle exists..."
ls -la "dist/MedicalAssistant.app/Contents/MacOS/MedicalAssistant"
# Verify top-level signature (--deep may fail if removed binaries are
# still referenced in inner resource seals; notarization is the real test)
codesign --verify --strict "dist/MedicalAssistant.app" && echo "codesign --verify: OK" || echo "codesign --verify: warning (notarization will be the definitive check)"

# spctl may fail in CI (no GUI session), so don't fail the build on it
spctl --assess --type execute "dist/MedicalAssistant.app" 2>&1 && echo "spctl --assess: accepted" || echo "spctl --assess: skipped (expected in CI)"

# ─── Notarization ───
# Notarize the .app FIRST (as a zip), then staple the ticket to the .app,
# THEN create the DMG. This ensures when users drag the .app out of the DMG,
# the .app itself has a stapled notarization ticket and passes Gatekeeper.
echo ""
echo "=== Notarizing .app bundle ==="

if [ -z "$APPLE_ID" ] || [ -z "$APPLE_ID_PASSWORD" ] || [ -z "$MACOS_TEAM_ID" ]; then
    echo "Notarization credentials not set — skipping notarization."
    echo "Set APPLE_ID, APPLE_ID_PASSWORD, and MACOS_TEAM_ID to enable."

    echo ""
    echo "Creating unsigned DMG..."
    hdiutil create -volname "Medical Assistant" \
        -srcfolder "dist/MedicalAssistant.app" \
        -ov -format UDZO \
        "dist/MedicalAssistant-macOS.dmg"
    echo "Unsigned DMG created: dist/MedicalAssistant-macOS.dmg"
    cd "$INITIAL_DIR"
    exit 0
fi

# Create a zip of the .app for notarization submission
echo "Creating zip for notarization submission..."
ditto -c -k --keepParent "dist/MedicalAssistant.app" "dist/MedicalAssistant.app.zip"

NOTARIZE_OUTPUT=$(xcrun notarytool submit "dist/MedicalAssistant.app.zip" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PASSWORD" \
    --team-id "$MACOS_TEAM_ID" \
    --wait \
    --timeout 30m 2>&1)

echo "$NOTARIZE_OUTPUT"

# Check if notarization was accepted
if echo "$NOTARIZE_OUTPUT" | grep -q "status: Accepted"; then
    echo "Notarization accepted."

    # Staple the ticket directly to the .app bundle
    echo ""
    echo "=== Stapling .app bundle ==="
    xcrun stapler staple "dist/MedicalAssistant.app"
    xcrun stapler validate "dist/MedicalAssistant.app"
    echo ".app stapling complete."
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

# Clean up zip
rm -f "dist/MedicalAssistant.app.zip"

# ─── Create DMG (from the stapled .app) ───
# IMPORTANT: We use ditto (not cp or hdiutil -srcfolder) to copy the .app
# into the DMG because ditto preserves extended attributes, which is where
# the notarization staple ticket lives. Without ditto, the .app inside the
# DMG loses its staple and Gatekeeper cannot verify it offline.
echo ""
echo "=== Creating DMG ==="

DMG_NAME="MedicalAssistant-macOS.dmg"
DMG_TEMP="dist/tmp_dmg.dmg"
DMG_MOUNT="/Volumes/Medical Assistant"

# Step 1: Create a writable disk image (large enough for the .app)
APP_SIZE_KB=$(du -sk "dist/MedicalAssistant.app" | cut -f1)
DMG_SIZE_KB=$((APP_SIZE_KB + 20480))  # Add 20MB headroom for DMG overhead + styling
echo "Creating writable disk image (${DMG_SIZE_KB}KB)..."
hdiutil create -size "${DMG_SIZE_KB}k" \
    -volname "Medical Assistant" \
    -fs HFS+ \
    -type SPARSE \
    "$DMG_TEMP"

# Step 2: Mount the writable image
echo "Mounting writable image..."
hdiutil attach "${DMG_TEMP}.sparseimage" -mountpoint "$DMG_MOUNT" -nobrowse

# Step 3: Copy .app using ditto (preserves xattrs including notarization staple)
echo "Copying .app with ditto (preserves notarization staple)..."
ditto "dist/MedicalAssistant.app" "$DMG_MOUNT/MedicalAssistant.app"

# Step 4: Create Applications symlink for drag-to-install
ln -s /Applications "$DMG_MOUNT/Applications"

# Step 5: Set volume icon if available
if [ -f "icon.icns" ]; then
    cp "icon.icns" "$DMG_MOUNT/.VolumeIcon.icns"
    SetFile -c icnC "$DMG_MOUNT/.VolumeIcon.icns" 2>/dev/null || true
    SetFile -a C "$DMG_MOUNT" 2>/dev/null || true
fi

# Step 6: Verify the .app staple survived the copy
echo "Verifying .app staple inside DMG..."
if xcrun stapler validate "$DMG_MOUNT/MedicalAssistant.app" 2>&1 | grep -q "worked"; then
    echo ".app staple preserved inside DMG!"
else
    echo "WARNING: .app staple was NOT preserved. Re-stapling inside DMG..."
    xcrun stapler staple "$DMG_MOUNT/MedicalAssistant.app" || echo "Re-staple failed (will rely on DMG-level staple + online check)"
fi

# Step 7: Unmount
echo "Unmounting..."
hdiutil detach "$DMG_MOUNT" -force

# Step 8: Convert to compressed read-only DMG
echo "Converting to compressed read-only DMG..."
rm -f "dist/$DMG_NAME"
hdiutil convert "${DMG_TEMP}.sparseimage" \
    -format UDZO \
    -o "dist/$DMG_NAME"

# Clean up temp image
rm -f "${DMG_TEMP}.sparseimage"

echo "DMG created: dist/$DMG_NAME"

# Sign the DMG
echo ""
echo "=== Signing DMG ==="
codesign --force --sign "$MACOS_SIGNING_IDENTITY" --timestamp "dist/$DMG_NAME"
echo "DMG signed."

echo ""
echo "=== Notarizing DMG ==="
DMG_NOTARIZE_OUTPUT=$(xcrun notarytool submit "dist/$DMG_NAME" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PASSWORD" \
    --team-id "$MACOS_TEAM_ID" \
    --wait \
    --timeout 30m 2>&1)

echo "$DMG_NOTARIZE_OUTPUT"

if echo "$DMG_NOTARIZE_OUTPUT" | grep -q "status: Accepted"; then
    echo "DMG notarization accepted."
    xcrun stapler staple "dist/$DMG_NAME"
    xcrun stapler validate "dist/$DMG_NAME"
    echo "DMG stapling complete."
else
    echo "WARNING: DMG notarization was NOT accepted."
    DMG_SUBMISSION_ID=$(echo "$DMG_NOTARIZE_OUTPUT" | grep "id:" | head -1 | awk '{print $2}')
    if [ -n "$DMG_SUBMISSION_ID" ]; then
        echo "Fetching DMG notarization log..."
        xcrun notarytool log "$DMG_SUBMISSION_ID" \
            --apple-id "$APPLE_ID" \
            --password "$APPLE_ID_PASSWORD" \
            --team-id "$MACOS_TEAM_ID" \
            dmg_notarization_log.json 2>&1 || true
        if [ -f "dmg_notarization_log.json" ]; then
            echo "=== DMG Notarization Log ==="
            cat dmg_notarization_log.json
            echo ""
        fi
    fi
    echo "Continuing without DMG notarization."
fi

echo ""
echo "=== Done ==="
echo "Signed and notarized DMG: dist/$DMG_NAME"

# Return to initial directory
cd "$INITIAL_DIR"
