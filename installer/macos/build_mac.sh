#!/usr/bin/env bash
# Build script for 3T Reader macOS .app + .dmg
# Usage:
#   ./installer/macos/build_mac.sh               # dev build, no signing
#   SIGN_ID="Developer ID Application: ..." \
#   NOTARIZE_TEAM="XXXXXXXXXX" \
#   NOTARIZE_APPLE_ID="you@email.com" \
#   NOTARIZE_PWD="app-specific-password" \
#   ./installer/macos/build_mac.sh               # signed + notarized

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SPEC="$REPO_ROOT/installer/macos/3T_Reader_mac.spec"
DIST_DIR="$REPO_ROOT/dist/mac"
APP_NAME="3T Reader"
APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/3T_Reader_mac.dmg"

echo "=== 3T Reader macOS build ==="
echo "Repo: $REPO_ROOT"

# ── 1. PyInstaller ──────────────────────────────────────────────
echo "[1/4] Building .app with PyInstaller..."
cd "$REPO_ROOT"
pyinstaller "$SPEC" --distpath "$DIST_DIR" --workpath "$REPO_ROOT/build/mac" --noconfirm
echo "      App bundle: $APP_PATH"

# ── 2. Code signing (optional) ──────────────────────────────────
if [[ -n "${SIGN_ID:-}" ]]; then
    echo "[2/4] Signing .app with: $SIGN_ID"
    codesign \
        --deep \
        --force \
        --options runtime \
        --entitlements "$REPO_ROOT/installer/macos/entitlements.plist" \
        --sign "$SIGN_ID" \
        "$APP_PATH"
    codesign --verify --deep --strict "$APP_PATH"
    echo "      Signing OK"
else
    echo "[2/4] Skipping signing (SIGN_ID not set)"
fi

# ── 3. DMG packaging ────────────────────────────────────────────
echo "[3/4] Creating .dmg..."
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --window-size 540 380 \
        --icon-size 128 \
        --app-drop-link 380 170 \
        --icon "$APP_NAME.app" 160 170 \
        "$DMG_PATH" \
        "$DIST_DIR/"
else
    # Fallback: plain hdiutil (no fancy layout)
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$DIST_DIR" \
        -ov -format UDZO \
        "$DMG_PATH"
fi
echo "      DMG: $DMG_PATH"

# ── 4. Notarization (optional) ──────────────────────────────────
if [[ -n "${SIGN_ID:-}" && -n "${NOTARIZE_APPLE_ID:-}" ]]; then
    echo "[4/4] Submitting for notarization..."
    xcrun notarytool submit "$DMG_PATH" \
        --apple-id "$NOTARIZE_APPLE_ID" \
        --password "$NOTARIZE_PWD" \
        --team-id "$NOTARIZE_TEAM" \
        --wait
    xcrun stapler staple "$DMG_PATH"
    echo "      Notarization OK"
else
    echo "[4/4] Skipping notarization (SIGN_ID / NOTARIZE_APPLE_ID not set)"
fi

echo ""
echo "=== Build complete ==="
echo "App: $APP_PATH"
echo "DMG: $DMG_PATH"
