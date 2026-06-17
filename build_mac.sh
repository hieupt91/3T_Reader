#!/bin/bash
set -e

echo "=== 3T READER MAC BUILD PIPELINE ==="

echo "1. Cleaning up old builds..."
rm -rf build dist

echo "2. Building .app with PyInstaller..."
python3 -m PyInstaller --noconfirm 3T_Reader.spec

echo "3. Packaging into .dmg using hdiutil..."
if [ -d "dist/3T Reader.app" ]; then
    hdiutil create -volname "3T Reader" -srcfolder "dist/3T Reader.app" -ov -format UDZO "dist/3T_Reader.dmg"
    echo "=== DMG BUILD COMPLETE! LOCATED AT: dist/3T_Reader.dmg ==="
else
    echo "ERROR: dist/3T Reader.app not found. Build failed."
    exit 1
fi
